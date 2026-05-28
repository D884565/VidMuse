import uuid
import json
import asyncio
from typing import Optional, BinaryIO
from fastapi import UploadFile, BackgroundTasks
from pydantic.experimental import pipeline
from sqlalchemy.orm import Session
from volcenginesdkarkruntime.resources.context import context

from backend.store import get_storage_client
from backend.v1.app.config.config import settings
from backend.store.obj.minio_client import get_minio_client
from backend.v1.app.rag.core.pipline import VideoParsingPipeline, ProductParsingPipeline
from backend.v1.app.rag.dao.asset_dao import AssetDAO
from backend.framework.exceptions.exceptions import BusinessException, BaseAppException
from backend.framework.exceptions.error_codes import PARAM_ERROR
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ImageUnderstandingRequest, VideoUnderstandingRequest
from backend.store.database.sync_database import SessionLocal  # 导入session工厂


class AssetService:
    """资产业务逻辑层"""

    # 类型映射
    TYPE_NAME = {
        1: "图片",
        2: "视频",
        3: "音频"
    }

    @staticmethod
    def _validate_file(file: UploadFile, asset_type: int) -> str:
        """
        验证文件合法性
        :param file: 上传的文件
        :param asset_type: 资产类型
        :return: 文件扩展名
        """
        if file.size and file.size > settings.UPLOAD_MAX_SIZE:
            raise BusinessException(PARAM_ERROR, f"文件大小不能超过{settings.UPLOAD_MAX_SIZE / 1024 / 1024}MB")

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        allowed_exts = settings.ALLOWED_EXTENSIONS.get(asset_type, [])
        if not allowed_exts:
            raise BusinessException(PARAM_ERROR, "无效的资产类型")

        if ext not in allowed_exts:
            raise BusinessException(PARAM_ERROR, f"文件格式不允许，允许的格式: {', '.join(allowed_exts)}")

        return ext

    @staticmethod
    def generate_object_name(asset_type: int, ext: str, is_internal: bool = False) -> str:
        """生成对象存储路径"""
        type_dir = {1: "img", 2: "video", 3: "audio"}.get(asset_type, "other")
        uuid_str = str(uuid.uuid4()).replace("-", "")
        if is_internal:
            return f"materials/{type_dir}/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"
        return f"assets/{type_dir}/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"

    @staticmethod
    async def _extract_ai_features(id: int, asset_type: int) -> dict:
        """
        提取AI特征
        :param file_url: 文件的公网访问URL
        :param asset_type: 资产类型 1-图片 2-视频 3-音频
        :return: AI特征字典
        """
        try:
            if asset_type == 1:  # 图片
                pipeline = ProductParsingPipeline ()
                content = pipeline.run({"image": id})
            elif asset_type == 2:  # 视频
                pipeline = VideoParsingPipeline()
                content = pipeline.run({"video": id})
            elif asset_type == 3:  # 音频
                # todo 后期实现音频解析
                return {
                    "scene": "音频",
                    "mood": "未知",
                    "objects": ["声音"]
                }
            else:
                return {
                    "scene": "未知",
                    "mood": "未知",
                    "objects": []
                }

            try:

                if not isinstance(content, dict):
                    raise ValueError("返回结果不是字典")
                required_fields = ["scene", "mood", "objects"]
                for field in required_fields:
                    if field not in content:
                        raise ValueError(f"返回结果缺少必要字段: {field}")
                if not isinstance(content["objects"], list):
                    content["objects"] = [tag.strip() for tag in str(content["objects"]).split(",")]

                return content
            except (json.JSONDecodeError, ValueError):
                return {
                    "scene": "未知",
                    "mood": "未知",
                    "objects": ["自动生成"]
                }

        except BaseAppException:
            return {
                "error": "解析特征失败"
            }





    @staticmethod
    async def upload_user_asset(
            db: Session,
            background_tasks: BackgroundTasks,
            file: UploadFile,
            type: int,
            title: Optional[str] = None,
            source_type: int = 0
    ) -> dict:
        """【用户端】上传资产到个人素材库"""
        # 参数校验
        if type not in [1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的资产类型，支持: 1-图片, 2-视频, 3-音频")
        if source_type not in [0, 1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的来源类型，支持: 0-用户上传, 1-AI生成, 2-爬取, 3-购买")

        # 验证文件
        ext = AssetService._validate_file(file, type)

        # 生成用户资产存储路径
        object_name = AssetService._generate_object_name(type, file.filename, ext,is_internal=False)

        # 上传到存储
        client = get_storage_client()
        file_url = client.upload_fileobj(
            file=file.file,
            object_name=object_name,
            content_type=file.content_type
        )

        # 生成默认标题
        if not title:
            title = file.filename or f"{AssetService.TYPE_NAME.get(type, '素材')}_{uuid.uuid4().hex[:8]}"


        # 准备数据，AI特征先设为None，后续异步更新
        asset_data = {
            "type": type,
            "title": title.strip(),
            "url": file_url,
            "file_size": file.size,
            # 时长由解析通道完成
            "duration": None,
            "format": ext,
            "ai_features": None,
            "source_type": source_type,
            "user_id": 10001  # 暂时固定用户ID，待用户系统实现后替换
        }

        # 创建资产记录
        asset = AssetDAO.create_asset(db, asset_data)
        asset_dict = asset.to_dict()


        # 传入视频id
        context = await AssetService._extract_ai_features(asset.id, asset.type)


        # todo 目前先将解析结果落库，后续再优化
        slices = []
        for i in range(context["slice_len"]):
            context["slice_id"] = i
            response_data = {
                "id": asset_dict["id"],
                "type": asset_dict["type"],
                "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
                "title": asset_dict["title"],
                "url": asset_dict["url"],
                "file_size": asset_dict["file_size"],
                "duration": asset_dict["duration"],
                "format": asset_dict["format"],
                "ai_features": context["ai_features"],
                "source_type": asset_dict["source_type"],
                "created_at": asset_dict["created_at"]
            }
            slices.append(response_data)
        AssetDAO.insert_batch_assets(db, slices)



        # 构造响应数据
        response_data = {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "file_size": asset_dict["file_size"],
            "duration": asset_dict["duration"],
            "format": asset_dict["format"],
            "ai_features": context["ai_features"],
            "source_type": asset_dict["source_type"],
            "created_at": asset_dict["created_at"]
        }

        return response_data

    @staticmethod
    async def upload_internal_asset(
            db: Session,
            file: UploadFile,
            type: int,
            title: Optional[str] = None,
            source_type: int = 1,
            skip_ai_analysis: bool = True
    ) -> dict:
        """【后台内部】上传系统内部资产"""
        # 参数校验
        if type not in [1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的资产类型，支持: 1-图片, 2-视频, 3-音频")
        if source_type not in [0, 1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的来源类型，支持: 0-上传, 1-AI生成, 2-系统预置, 3-其他")

        # 验证文件
        ext = AssetService._validate_file(file, type)

        # 生成内部资产存储路径
        object_name = AssetService._generate_object_name(type, file.filename, ext,is_internal=True)

        # 上传到存储
        client = get_storage_client()
        file_url = client.upload_fileobj(
            file=file.file,
            object_name=object_name,
            content_type=file.content_type
        )

        # 生成默认标题
        if not title:
            title = file.filename or f"系统{AssetService.TYPE_NAME.get(type, '素材')}_{uuid.uuid4().hex[:8]}"



        # 准备数据
        asset_data = {
            "type": type,
            "title": title.strip(),
            "url": file_url,
            "file_size": file.size,
            "duration": None,
            "format": ext,
            "ai_features": None,
            "source_type": source_type,
            "user_id": 0  # 系统用户ID，0表示内部资产
        }


        # 创建资产记录
        asset = AssetDAO.create_asset(db, asset_data)
        asset_dict = asset.to_dict()


        # 如果不需要跳过AI分析，则同步提取特征（内部接口可以接受稍长时间）
        if not skip_ai_analysis:
            context = await AssetService._extract_ai_features(asset_dict["id"], type)
            asset_data["ai_features"] = context["ai_features"]

        # 构造响应数据
        response_data = {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "file_size": asset_dict["file_size"],
            "duration": asset_dict["duration"],
            "format": asset_dict["format"],
            "ai_features": asset_dict["ai_features"],
            "source_type": asset_dict["source_type"],
            "created_at": asset_dict["created_at"]
        }

        return response_data

    @staticmethod
    def list_assets(
            db: Session,
            type: Optional[int] = None,
            source_type: Optional[int] = None,
            keyword: Optional[str] = None,
            format: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> dict:
        """查询资产列表"""
        # 参数校验
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        if type is not None and type not in [1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的资产类型")
        if source_type is not None and source_type not in [0, 1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的来源类型")

        # 查询数据
        total, assets = AssetDAO.list_assets(
            db=db,
            user_id=10001,  # 暂时固定用户ID，待用户系统实现后替换
            type=type,
            source_type=source_type,
            keyword=keyword,
            format=format,
            page=page,
            page_size=page_size
        )

        # 转换为响应格式
        asset_list = []
        for asset in assets:
            asset_dict = asset.to_dict()
            list_item = {
                "id": asset_dict["id"],
                "type": asset_dict["type"],
                "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
                "title": asset_dict["title"],
                "url": asset_dict["url"],
                "file_size": asset_dict["file_size"],
                "duration": asset_dict["duration"],
                "format": asset_dict["format"],
                "ai_features": asset_dict["ai_features"],
                "source_type": asset_dict["source_type"],
                "created_at": asset_dict["created_at"]
            }
            asset_list.append(list_item)

        return {
            "list": asset_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
            }
        }

    @staticmethod
    def get_asset_detail(db: Session, asset_id: int) -> dict:
        """获取资产详情"""
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "资产不存在")

        asset_dict = asset.to_dict()
        return asset_dict

    @staticmethod
    def update_asset(
            db: Session,
            asset_id: int,
            title: Optional[str] = None,
            ai_features: Optional[dict] = None
    ) -> dict:
        """更新资产信息"""
        # 检查资产是否存在
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "资产不存在")

        # 准备更新数据
        update_data = {}

        if title is not None:
            title = title.strip()
            if len(title) == 0:
                raise BusinessException(PARAM_ERROR, "资产标题不能为空")
            if len(title) > 200:
                raise BusinessException(PARAM_ERROR, "资产标题不能超过200字符")
            update_data["title"] = title

        if ai_features is not None:
            if not isinstance(ai_features, dict):
                raise BusinessException(PARAM_ERROR, "ai_features必须是JSON对象")
            update_data["ai_features"] = ai_features

        # 如果没有要更新的字段，直接返回
        if not update_data:
            return {
                "id": asset.id,
                "title": asset.title,
                "updated_at": asset.created_at.isoformat() + "Z"
            }

        # 执行更新
        updated_asset = AssetDAO.update_asset(db, asset_id, update_data)

        return {
            "id": updated_asset.id,
            "title": updated_asset.title,
            "updated_at": updated_asset.created_at.isoformat() + "Z"
        }

    @staticmethod
    def delete_asset(db: Session, asset_id: int) -> None:
        """删除资产"""
        # 检查资产是否存在
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "资产不存在")

        # 删除存储中的文件
        client = get_storage_client()
        try:
            # 从URL中提取object_name
            if asset.url and client.bucket_name in asset.url:
                object_name = asset.url.split(f"{client.bucket_name}/")[-1]
                client.delete_object(object_name)
        except Exception:
            # 忽略存储删除失败的情况，继续删除数据库记录
            pass

        # 执行删除
        success = AssetDAO.delete_asset(db, asset_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")

    @classmethod
    def _generate_object_name(cls, type,  file_name ,ext, is_internal) ->str:
        mappings = {
            1: "image",
            2: "video",
            3: "audio"
        }
        if is_internal:
            return f"material/{mappings[type]}/{file_name}.{ext}"
        else:
            return f"assets/{mappings[type]}/{file_name}.{ext}"
        return ""
