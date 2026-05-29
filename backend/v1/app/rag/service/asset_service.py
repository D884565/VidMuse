import os
import uuid
import json
import asyncio
from typing import Optional, BinaryIO
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from backend.store import get_storage_client
from backend.v1.app.config.config import settings
from backend.v1.app.rag.core.pipline import VideoParsingPipeline, ProductParsingPipeline
from backend.v1.app.rag.dao.asset_dao import AssetDAO
from backend.framework.exceptions.exceptions import BusinessException, BaseAppException
from backend.framework.exceptions.error_codes import PARAM_ERROR


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
        # 检查文件大小，注意：FastAPI的UploadFile.size可能为None
        file_size = getattr(file, 'size', None)
        if file_size is not None and file_size > settings.UPLOAD_MAX_SIZE:
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
    async def _extract_ai_features(id: int, asset_type: int, asset_url: str = None) -> dict:
        """
        提取AI特征
        :param id: 资产ID
        :param asset_type: 资产类型 1-图片 2-视频 3-音频
        :param asset_url: 资产的存储URL
        :return: AI特征字典
        """
        try:
            if asset_type == 1:  # 图片
                # todo 产品解析流水线目前参数不匹配，暂时返回模拟数据
                return {
                    "scene": "商品图片",
                    "mood": "商业",
                    "objects": ["商品"],
                    "slice_len": 1,
                    "ai_features": {
                        "scene": "商品图片",
                        "mood": "商业",
                        "objects": ["商品"]
                    }
                }
            elif asset_type == 2:  # 视频
                pipeline = VideoParsingPipeline()
                # 从URL中提取object_name
                from backend.store import get_storage_client
                client = get_storage_client()
                object_name = None
                if asset_url and client.get_bucket_name() in asset_url:
                    object_name = asset_url.split(f"{client.get_bucket_name()}/")[-1]
                result = pipeline.run({
                    "video_id": id,
                    "video_url": asset_url,
                    "object_name": object_name
                })
                if not result.get("success", False):
                    raise ValueError(f"视频解析失败: {result.get('errors', [])}")
                content = result.get("data", {})
            elif asset_type == 3:  # 音频
                # todo 后期实现音频解析
                return {
                    "scene": "音频",
                    "mood": "未知",
                    "objects": ["声音"],
                    "slice_len": 1,
                    "ai_features": {
                        "scene": "音频",
                        "mood": "未知",
                        "objects": ["声音"]
                    }
                }
            else:
                return {
                    "scene": "未知",
                    "mood": "未知",
                    "objects": [],
                    "slice_len": 1,
                    "ai_features": {
                        "scene": "未知",
                        "mood": "未知",
                        "objects": []
                    }
                }

            try:
                if not isinstance(content, dict):
                    raise ValueError("返回结果不是字典")

                # 确保返回结果包含必要的字段
                result = {
                    "slice_len": content.get("slice_len", 1),
                    "ai_features": content.get("ai_features", {}),
                    "scene": content.get("scene", "未知"),
                    "mood": content.get("mood", "未知"),
                    "objects": content.get("objects", [])
                }

                # 如果有切片信息也保留
                if "slices" in content:
                    result["slices"] = content["slices"]

                # 处理objects字段
                if not isinstance(result["objects"], list):
                    result["objects"] = [tag.strip() for tag in str(result["objects"]).split(",")]

                # 确保ai_features包含基本字段
                if not isinstance(result["ai_features"], dict):
                    result["ai_features"] = {}
                if "scene" not in result["ai_features"]:
                    result["ai_features"]["scene"] = result["scene"]
                if "mood" not in result["ai_features"]:
                    result["ai_features"]["mood"] = result["mood"]
                if "objects" not in result["ai_features"]:
                    result["ai_features"]["objects"] = result["objects"]

                return result
            except (json.JSONDecodeError, ValueError):
                return {
                    "scene": "未知",
                    "mood": "未知",
                    "objects": ["自动生成"],
                    "slice_len": 1,
                    "ai_features": {
                        "scene": "未知",
                        "mood": "未知",
                        "objects": ["自动生成"]
                    }
                }

        except Exception as e:
            return {
                "error": f"解析特征失败: {str(e)}",
                "slice_len": 1,
                "ai_features": {
                    "error": f"解析特征失败: {str(e)}"
                }
            }

    @staticmethod
    async def _process_asset_parsing(db: Session, asset_id: int, asset_type: int, asset_url: str, asset_dict: dict = None) -> dict:
        """
        处理资产解析逻辑：提取AI特征、生成切片、保存到数据库
        :param db: 数据库会话
        :param asset_id: 资产ID
        :param asset_type: 资产类型
        :param asset_url: 资产URL
        :param asset_dict: 资产字典（可选，避免重复查询）
        :return: 解析结果上下文
        """
        # 提取AI特征
        context = await AssetService._extract_ai_features(asset_id, asset_type, asset_url)

        # 处理切片逻辑 - 只针对视频类型
        if asset_type == 2 and context.get("slice_len", 0) > 0:
            from backend.v1.app.slice.dao.slice_dao import SliceDAO

            slices = []
            for i in range(context["slice_len"]):
                # 处理多切片情况，优先取对应切片的特征
                slice_list = context.get("slices", [])
                if i < len(slice_list):
                    # 有详细的切片信息
                    slice_info = slice_list[i]
                    slice_features = slice_info.get("ai_features", context["ai_features"])
                    slice_data = {
                        "asset_id": asset_id,
                        "index": i + 1,
                        "title": slice_info.get("title", f"{asset_dict['title'] if asset_dict else '资产'}_切片_{i+1}"),
                        "url": slice_info.get("url", asset_url),
                        "cover_url": slice_info.get("cover_url"),
                        "start_time": slice_info.get("start_time"),
                        "end_time": slice_info.get("end_time"),
                        "duration": slice_info.get("duration", asset_dict["duration"] if asset_dict else None),
                        "ai_features": slice_features
                    }
                else:
                    # 没有详细切片信息，使用默认值
                    slice_features = context["ai_features"]
                    slice_data = {
                        "asset_id": asset_id,
                        "index": i + 1,
                        "title": f"{asset_dict['title'] if asset_dict else '资产'}_切片_{i+1}",
                        "url": asset_url,
                        "ai_features": slice_features,
                        "duration": asset_dict["duration"] if asset_dict else None
                    }
                slices.append(slice_data)

            # 批量插入切片到slices表
            if slices:
                SliceDAO.create_slices_batch(db, slices)

        # 更新原始资产的AI特征
        update_data = {"ai_features": context["ai_features"]}
        # 如果解析结果包含时长，也更新
        if "duration" in context and context["duration"] is not None:
            update_data["duration"] = context["duration"]

        AssetDAO.update_asset(db, asset_id, update_data)

        return context





    @staticmethod
    def _upload_asset_common(
            db: Session,
            file: UploadFile,
            type: int,
            title: Optional[str] = None,
            source_type: int = 0,
            is_internal: bool = False,
            user_id: int = None
    ) -> tuple[dict, dict]:
        """
        通用上传逻辑：文件验证、存储上传、创建数据库记录
        :param db: 数据库会话
        :param file: 上传文件
        :param type: 资产类型
        :param title: 资产标题
        :param source_type: 来源类型
        :param is_internal: 是否为内部资产
        :param user_id: 用户ID，内部资产默认为None
        :return: (资产字典, 存储路径信息)
        """
        # 参数校验
        if type not in [1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的资产类型，支持: 1-图片, 2-视频, 3-音频")
        if source_type not in [0, 1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "无效的来源类型，支持: 0-用户上传, 1-AI生成, 2-爬取, 3-购买")

        # 验证文件
        ext = AssetService._validate_file(file, type)

        # 生成存储路径
        object_name = AssetService.generate_object_name(asset_type=type, ext=ext, is_internal=is_internal)

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

        # 准备数据
        asset_data = {
            "type": type,
            "title": title.strip(),
            "url": file_url,
            "file_size": getattr(file, 'size', None),
            "duration": None,
            "format": ext,
            "ai_features": None,
            "source_type": source_type,
            "user_id": user_id
        }

        # 创建资产记录
        asset = AssetDAO.create_asset(db, asset_data)
        asset_dict = asset.to_dict()

        return asset_dict, {"object_name": object_name, "file_url": file_url}

    @staticmethod
    async def upload_user_asset(
            db: Session,
            background_tasks: BackgroundTasks,
            file: UploadFile,
            type: int,
            title: Optional[str] = None,
            source_type: int = 0,
            skip_analysis: bool = False
    ) -> dict:
        """【用户端】上传资产到个人素材库"""
        # 调用通用上传逻辑
        asset_dict, storage_info = AssetService._upload_asset_common(
            db=db,
            file=file,
            type=type,
            title=title,
            source_type=source_type,
            is_internal=False,
            user_id=10001  # 暂时固定用户ID，待用户系统实现后替换
        )

        context = None
        if not skip_analysis:
            # 执行解析
            context = await AssetService._process_asset_parsing(
                db=db,
                asset_id=asset_dict["id"],
                asset_type=asset_dict["type"],
                asset_url=asset_dict["url"],
                asset_dict=asset_dict
            )

        # 构造响应数据
        response_data = {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "file_size": asset_dict["file_size"],
            "duration": context.get("duration", asset_dict["duration"]) if context else asset_dict["duration"],
            "format": asset_dict["format"],
            "ai_features": context["ai_features"] if context else None,
            "source_type": asset_dict["source_type"],
            "created_at": asset_dict["created_at"],
            "analysis_performed": not skip_analysis
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
        object_name = AssetService.generate_object_name(asset_type=type, ext=ext, is_internal=True)

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
            "file_size": getattr(file, 'size', None),
            "duration": None,
            "format": ext,
            "ai_features": None,
            "source_type": source_type,
            "user_id": None  # 系统内部资产，NULL表示不属于任何用户
        }


        # 创建资产记录
        asset = AssetDAO.create_asset(db, asset_data)
        asset_dict = asset.to_dict()


        # 如果不需要跳过AI分析，则同步提取特征（内部接口可以接受稍长时间）
        if not skip_ai_analysis:
            context = await AssetService._extract_ai_features(asset_dict["id"], type, asset_dict["url"])
            ai_features = context["ai_features"]
            # 更新数据库中的ai_features字段
            updated_asset = AssetDAO.update_asset(db, asset_dict["id"], {"ai_features": ai_features})
            asset_dict = updated_asset.to_dict()

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
            "updated_at": updated_asset.created_at + "Z"
        }

    @staticmethod
    async def parse_asset(db: Session, asset_id: int, force: bool = False) -> dict:
        """
        手动触发资产解析
        :param db: 数据库会话
        :param asset_id: 资产ID
        :param force: 是否强制重新解析，即使已经解析过
        :return: 解析结果
        """
        # 获取资产信息
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "资产不存在")

        # 检查是否已经解析过
        if asset.ai_features is not None and not force:
            raise BusinessException(PARAM_ERROR, "资产已经解析过，如需重新解析请指定force=true")

        # 执行解析
        context = await AssetService._process_asset_parsing(
            db=db,
            asset_id=asset.id,
            asset_type=asset.type,
            asset_url=asset.url,
            asset_dict=asset.to_dict()
        )

        # 返回最新的资产信息
        updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
        asset_dict = updated_asset.to_dict()

        return {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "未知"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "duration": asset_dict["duration"],
            "ai_features": asset_dict["ai_features"],
            "analysis_completed": True
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
            if asset.url and client.get_bucket_name() in asset.url:
                object_name = asset.url.split(f"{client.get_bucket_name()}/")[-1]
                client.delete_object(object_name)
        except Exception:
            # 忽略存储删除失败的情况，继续删除数据库记录
            pass

        # 执行删除
        success = AssetDAO.delete_asset(db, asset_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")




