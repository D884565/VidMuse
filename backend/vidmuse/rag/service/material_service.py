import os
import uuid
import json

from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.vidmuse.config.settings import settings
from backend.vidmuse.core.minio_client import get_minio_client
from backend.vidmuse.rag.dao.material_dao import MaterialDAO
from backend.framework.exception.exceptions import BusinessException
from backend.framework.errorcode.error_codes import PARAM_ERROR
from backend.vidmuse.provider import VolcanoLLM, ImageUnderstandingRequest, VideoUnderstandingRequest
from backend.framework.exception.exceptions import BaseAppException


class MaterialService:
    """素材业务逻辑层"""

    @staticmethod
    def _validate_file(file: UploadFile, material_type: int) -> str:
        """
        验证文件合法性
        :param file: 上传的文件
        :param material_type: 素材类型
        :return: 文件扩展名
        """
        # 检查文件大小
        if file.size and file.size > settings.UPLOAD_MAX_SIZE:
            raise BusinessException(PARAM_ERROR, f"文件大小不能超过{settings.UPLOAD_MAX_SIZE / 1024 / 1024}MB")

        # 获取文件扩展名
        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        # 检查文件扩展名是否允许
        allowed_exts = settings.ALLOWED_EXTENSIONS.get(material_type, [])
        if not allowed_exts:
            raise BusinessException(PARAM_ERROR, "无效的素材类型")

        if ext not in allowed_exts:
            raise BusinessException(PARAM_ERROR, f"文件格式不允许，允许的格式: {', '.join(allowed_exts)}")

        return ext

    @staticmethod
    def _generate_object_name(material_type: int, ext: str) -> str:
        """
        生成对象存储路径
        :param material_type: 素材类型
        :param ext: 文件扩展名
        :return: 对象存储路径
        """
        type_dir = {1: "image", 2: "video", 3: "audio"}.get(material_type, "other")
        filename = f"{uuid.uuid4().hex}.{ext}"
        return f"materials/{type_dir}/{filename[:2]}/{filename[2:4]}/{filename}"

    @staticmethod
    async def _extract_ai_features(file_url: str, material_type: int) -> dict:
        """
        提取AI特征
        :param file_url: 文件的公网访问URL
        :param material_type: 素材类型 1-图片 2-视频 3-音频
        :return: AI特征，包含description和tags字段
        """
        try:
            # 初始化LLM客户端
            llm = VolcanoLLM(key=None, model_name=None)

            # 统一的提示词，要求返回JSON格式，包含描述和标签
            base_prompt = """请分析这个{media_type}的内容，返回JSON格式结果，包含两个字段：
1. description：详细的内容描述，100-150字
2. tags：相关的标签列表，5个标签，每个标签不超过5个字

返回结果只需要JSON，不需要其他内容。"""

            if material_type == 1:  # 图片
                prompt = base_prompt.format(media_type="图片")
                request = ImageUnderstandingRequest(
                    image_url=file_url,
                    prompt=prompt,
                    max_tokens=1024,
                    temperature=0.3,
                    top_p=0.9
                )
                response = llm.image_understanding(request)
            elif material_type == 2:  # 视频
                prompt = base_prompt.format(media_type="视频")
                request = VideoUnderstandingRequest(
                    video_url=file_url,
                    prompt=prompt,
                    max_tokens=1024,
                    temperature=0.3,
                    top_p=0.9
                )
                # 异步调用视频理解接口
                response = await llm.video_understanding(request)
            elif material_type == 3:  # 音频
                # 音频理解接口暂未实现，返回基础信息
                return {
                    "description": "音频素材，包含声音内容",
                    "tags": ["音频", "声音", "音乐"]
                }
            else:
                return {
                    "description": "未知类型素材",
                    "tags": ["其他"]
                }

            # 解析AI返回的JSON内容
            try:
                # 尝试提取JSON部分（可能包含markdown标记）
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()

                result = json.loads(content)
                # 确保返回格式正确
                if not isinstance(result, dict):
                    raise ValueError("返回结果不是字典")
                if "description" not in result or "tags" not in result:
                    raise ValueError("返回结果缺少必要字段")
                if not isinstance(result["tags"], list):
                    result["tags"] = [tag.strip() for tag in str(result["tags"]).split(",")]

                return result
            except (json.JSONDecodeError, ValueError):
                # 解析失败时，直接使用返回内容作为描述，自动生成标签
                return {
                    "description": response.content[:200],
                    "tags": ["自动生成"]
                }

        except BaseAppException:
            # AI服务调用失败时，返回默认值，不影响主流程
            return {
                "description": f"{'图片' if material_type == 1 else '视频' if material_type == 2 else '音频'}素材",
                "tags": ["素材"]
            }

    @staticmethod
    def _get_file_duration(file: UploadFile, material_type: int) -> Optional[int]:
        """
        获取音视频文件时长（模拟实现）
        :param file: 上传的文件
        :param material_type: 素材类型
        :return: 时长（秒）
        """
        # TODO: 实际项目中需要使用ffmpeg等工具获取时长
        if material_type in [2, 3]:
            return 15  # 模拟15秒
        return None

    @staticmethod
    async def upload_material(
            db: Session,
            file: UploadFile,
            material_type: int,
            title: str,
            tags: Optional[str] = None,
            source_type: int = 1
    ) -> dict:
        """
        上传素材
        :param db: 数据库会话
        :param file: 上传的文件
        :param material_type: 素材类型 1-图片 2-视频 3-音频
        :param title: 素材标题
        :param tags: 标签，逗号分隔
        :param source_type: 来源类型
        :return: 素材信息
        """
        # 验证文件
        ext = MaterialService._validate_file(file, material_type)

        # 生成对象存储路径
        object_name = MaterialService._generate_object_name(material_type, ext)

        # 上传文件到MinIO

        minio_client = get_minio_client()
        file_url = minio_client.upload_fileobj(
            file=file,
            object_name=object_name,
            content_type=file.content_type
        )

        presigned_url = minio_client.get_presigned_url(object_name)

        # 提取AI特征
        ai_features = await MaterialService._extract_ai_features(presigned_url, material_type)

        # 如果有用户传入的标签，合并到AI特征中
        if tags:
            user_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if user_tags:
                ai_features["tags"] = list(set(ai_features.get("tags", []) + user_tags))

        # 获取文件时长
        duration = MaterialService._get_file_duration(file, material_type)

        # 保存到数据库
        material_data = {
            "type": material_type,
            "title": title,
            "url": file_url,
            "file_size": file.size,
            "duration": duration,
            "format": ext,
            "ai_features": ai_features,
            "source_type": source_type
        }

        material = MaterialDAO.create_material(db, material_data)

        # 返回结果
        result = material.to_dict()
        return result

    @staticmethod
    def list_materials(
            db: Session,
            material_type: Optional[int] = None,
            keyword: Optional[str] = None,
            uploader_id: Optional[int] = None,
            page: int = 1,
            page_size: int = 20
    ) -> dict:
        """
        查询素材列表
        :param db: 数据库会话
        :param material_type: 素材类型筛选
        :param keyword: 标题/标签关键词搜索
        :param uploader_id: 上传者ID筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果
        """
        # 参数校验
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        total, materials = MaterialDAO.list_materials(
            db=db,
            material_type=material_type,
            keyword=keyword,
            uploader_id=uploader_id,
            page=page,
            page_size=page_size
        )

        # 转换为字典列表，仅保留需要的字段
        material_list = []
        for material in materials:
            material_dict = material.to_dict()
            # 仅保留示例中需要的字段
            filtered_material = {
                "id": material_dict["id"],
                "type": material_dict["type"],
                "title": material_dict["title"],
                "url": material_dict["url"],
                "duration": material_dict["duration"],
                "format": material_dict["format"],
                "source_type": material_dict["source_type"]
            }
            material_list.append(filtered_material)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "list": material_list
        }

    @staticmethod
    def delete_material(
            db: Session,
            material_id: int,
            current_user_id: Optional[int] = None
    ) -> None:
        """
        删除素材
        :param db: 数据库会话
        :param material_id: 素材ID
        :param current_user_id: 当前操作用户ID（用于权限校验）
        """
        # 检查素材是否存在
        material = MaterialDAO.get_material_by_id(db, material_id)
        if not material:
            raise BusinessException(PARAM_ERROR, "素材不存在")

        # TODO: 权限校验 - 仅上传者或管理员可以删除
        # 待表结构添加uploader_id字段后实现
        # if material.uploader_id != current_user_id and not current_user.is_admin:
        #     raise BusinessException(FORBIDDEN, "无权限删除该素材")

        # 执行删除
        success = MaterialDAO.delete_material(db, material_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")


