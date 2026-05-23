import uuid
import json

from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.v1.app.config.config import settings
from backend.v1.app.core.minio_client import get_minio_client
from backend.v1.app.rag.dao.material_dao import MaterialDAO
from backend.framework.exceptions.exceptions import BusinessException, BaseAppException
from backend.framework.exceptions.error_codes import PARAM_ERROR
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ImageUnderstandingRequest, VideoUnderstandingRequest


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
        if file.size and file.size > settings.UPLOAD_MAX_SIZE:
            raise BusinessException(PARAM_ERROR, f"文件大小不能超过{settings.UPLOAD_MAX_SIZE / 1024 / 1024}MB")

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        allowed_exts = settings.ALLOWED_EXTENSIONS.get(material_type, [])
        if not allowed_exts:
            raise BusinessException(PARAM_ERROR, "无效的素材类型")

        if ext not in allowed_exts:
            raise BusinessException(PARAM_ERROR, f"文件格式不允许，允许的格式: {', '.join(allowed_exts)}")

        return ext

    @staticmethod
    def _generate_object_name(material_type: int, ext: str) -> str:
        """生成对象存储路径"""
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
            llm = VolcanoLLM(key=None, model_name=None)

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
                response = await llm.video_understanding(request)
            elif material_type == 3:  # 音频
                return {
                    "description": "音频素材，包含声音内容",
                    "tags": ["音频", "声音", "音乐"]
                }
            else:
                return {
                    "description": "未知类型素材",
                    "tags": ["其他"]
                }

            try:
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()

                result = json.loads(content)
                if not isinstance(result, dict):
                    raise ValueError("返回结果不是字典")
                if "description" not in result or "tags" not in result:
                    raise ValueError("返回结果缺少必要字段")
                if not isinstance(result["tags"], list):
                    result["tags"] = [tag.strip() for tag in str(result["tags"]).split(",")]

                return result
            except (json.JSONDecodeError, ValueError):
                return {
                    "description": response.content[:200],
                    "tags": ["自动生成"]
                }

        except BaseAppException:
            return {
                "description": f"{'图片' if material_type == 1 else '视频' if material_type == 2 else '音频'}素材",
                "tags": ["素材"]
            }

    @staticmethod
    def _get_file_duration(file: UploadFile, material_type: int) -> Optional[int]:
        """获取音视频文件时长（模拟实现）"""
        if material_type in [2, 3]:
            return 15
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
        """上传素材"""
        ext = MaterialService._validate_file(file, material_type)
        object_name = MaterialService._generate_object_name(material_type, ext)

        minio_client = get_minio_client()
        file_url = minio_client.upload_fileobj(
            file=file,
            object_name=object_name,
            content_type=file.content_type
        )

        presigned_url = minio_client.get_presigned_url(object_name)

        ai_features = await MaterialService._extract_ai_features(presigned_url, material_type)

        if tags:
            user_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if user_tags:
                ai_features["tags"] = list(set(ai_features.get("tags", []) + user_tags))

        duration = MaterialService._get_file_duration(file, material_type)

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
        return material.to_dict()

    @staticmethod
    def list_materials(
            db: Session,
            material_type: Optional[int] = None,
            keyword: Optional[str] = None,
            uploader_id: Optional[int] = None,
            page: int = 1,
            page_size: int = 20
    ) -> dict:
        """查询素材列表"""
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

        material_list = []
        for material in materials:
            material_dict = material.to_dict()
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
        """删除素材"""
        material = MaterialDAO.get_material_by_id(db, material_id)
        if not material:
            raise BusinessException(PARAM_ERROR, "素材不存在")

        success = MaterialDAO.delete_material(db, material_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")
