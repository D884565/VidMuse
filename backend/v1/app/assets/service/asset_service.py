import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.framework.exceptions.error_codes import PARAM_ERROR
from backend.framework.exceptions.exceptions import BusinessException
from backend.store import get_storage_client
from backend.store.obj.local_client import get_local_storage_client
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.common.parsing.base_parsing_service import BaseParsingService
from backend.v1.app.pipeline.factory.pipeline_factory import PipelineFactory
# BasePipeline 导入移到函数内部，避免循环导入
from backend.v1.app.config.config import settings


class AssetService(BaseParsingService):
    TYPE_NAME = {
        1: "image",
        2: "video",
        3: "audio",
        4: "text",
    }

    # 实现BaseParsingService的抽象方法
    def get_pipeline(self, context: Dict[str, Any]) -> 'BasePipeline':
        """获取商品解析流水线，Assets模块统一使用ProductParsingPipeline"""
        # 延迟导入避免循环依赖
        from backend.v1.app.pipeline.base import BasePipeline
        asset_type = context.get("asset_type")
        return PipelineFactory.get_pipeline_for_asset_type(
            asset_type=asset_type,
            enable_persistence=True,
            persist_to_asset=True
        )

    def get_asset_id(self, db: Session, business_id: int, context: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Assets模块的业务ID就是资产ID"""
        return business_id

    def sync_status(self, db: Session, business_id: int, asset: Any) -> None:
        """Assets模块不需要同步到其他表，空实现"""
        pass

    @staticmethod
    def _library_owner_id(user_id: Optional[int]) -> Optional[int]:
        return user_id

    @staticmethod
    def detect_asset_type(file: UploadFile) -> int:
        content_type = file.content_type or ""
        if content_type.startswith("image/"):
            return 1
        if content_type.startswith("video/"):
            return 2
        if content_type.startswith("audio/"):
            return 3

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "heic"}
        video_exts = {"mp4", "avi", "mov", "flv", "wmv", "webm", "mkv"}
        audio_exts = {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"}
        if ext in image_exts:
            return 1
        if ext in video_exts:
            return 2
        if ext in audio_exts:
            return 3
        raise BusinessException(PARAM_ERROR, "unsupported file type")

    @staticmethod
    def _validate_file(file: UploadFile, asset_type: int) -> str:
        file_size = getattr(file, "size", None)
        if file_size is not None and file_size > settings.UPLOAD_MAX_SIZE:
            raise BusinessException(PARAM_ERROR, "file too large")

        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        allowed_exts = settings.ALLOWED_EXTENSIONS.get(asset_type, [])
        if asset_type not in [1, 2, 3]:
            raise BusinessException(PARAM_ERROR, "invalid asset type")
        if ext not in allowed_exts:
            raise BusinessException(PARAM_ERROR, "invalid file extension")
        return ext

    @staticmethod
    def generate_object_name(asset_type: int, ext: str, is_internal: bool = False) -> str:
        type_dir = {1: "img", 2: "video", 3: "audio"}.get(asset_type, "other")
        uuid_str = str(uuid.uuid4()).replace("-", "")
        root = "materials" if is_internal else "assets"
        return f"{root}/{type_dir}/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"

    @staticmethod
    def _default_upload_root() -> str:
        return os.path.join("test_output", "uploads")

    @staticmethod
    def _normalize_title(title: Optional[str], fallback: str) -> str:
        final_title = (title or fallback).strip()
        return final_title or fallback

    @staticmethod
    def _upload_file(file_path: str, object_name: str, content_type: Optional[str] = None) -> str:
        """直接上传文件到存储，不降级"""
        return get_storage_client().upload_file(file_path, object_name, content_type)

    @staticmethod
    def _upload_fileobj(file_obj, object_name: str, content_type: Optional[str] = None) -> str:
        """直接上传文件对象到存储，不降级"""
        stream = getattr(file_obj, "file", file_obj)
        if hasattr(stream, "seek"):
            stream.seek(0)
        return get_storage_client().upload_fileobj(stream, object_name, content_type)

    @staticmethod
    def _storage_for_asset_url(url: Optional[str]):
        if url and url.startswith(settings.LOCAL_STORAGE_URL_PREFIX):
            return get_local_storage_client()
        return get_storage_client()


    @staticmethod
    def create_text_asset(db: Session, user_id: int, title: Optional[str], content_text: str) -> dict:
        content = (content_text or "").strip()
        if not content:
            raise BusinessException(PARAM_ERROR, "text content cannot be empty")

        final_title = AssetService._normalize_title(title, "Untitled text asset")
        asset = AssetDAO.create_asset(
            db,
            {
                "user_id": AssetService._library_owner_id(user_id),
                "type": 4,
                "title": final_title,
                "url": "",
                "file_size": None,
                "duration": None,
                "format": "text",
                "ai_features": None,
                "content_text": content,
                "source_type": 0,
                "scope": {"type": "library"},
            },
        )
        AssetService._parse_asset_sync(db, asset.id, force=True)
        return AssetDAO.get_asset_by_id(db, asset.id).to_dict()

    @staticmethod
    def update_text_asset(db: Session, user_id: int, asset_id: int, title: Optional[str], content_text: str) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type != 4:
            raise BusinessException(PARAM_ERROR, "only text assets can be edited here")
        # 权限校验：只有所有者可以操作
        if asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")

        content = (content_text or "").strip()
        if not content:
            raise BusinessException(PARAM_ERROR, "text content cannot be empty")

        update_data = {"content_text": content}
        if title is not None:
            final_title = title.strip()
            if not final_title:
                raise BusinessException(PARAM_ERROR, "asset title cannot be empty")
            update_data["title"] = final_title

        updated_asset = AssetDAO.update_asset(db, asset_id, update_data)
        AssetService._parse_asset_sync(db, asset_id, force=True)
        return AssetDAO.get_asset_by_id(db, asset_id).to_dict()


    @staticmethod
    async def reupload_image_asset(
        db: Session,
        user_id: int,
        asset_id: int,
        file: UploadFile,
        title: Optional[str] = None,
    ) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type != 1:
            raise BusinessException(PARAM_ERROR, "only image assets support reupload")
        # 权限校验：只有所有者可以操作
        if asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")

        ext = AssetService._validate_file(file, 1)
        object_name = AssetService.generate_object_name(asset_type=1, ext=ext)
        file_url = AssetService._upload_fileobj(file.file, object_name, file.content_type)

        old_storage_key = asset.storage_key
        old_storage = AssetService._storage_for_asset_url(asset.url)
        updated_asset = AssetDAO.update_asset(
            db,
            asset_id,
            {
                "title": AssetService._normalize_title(title, asset.title or file.filename or "Untitled asset"),
                "url": file_url,
                "file_size": getattr(file, "size", None),
                "format": ext,
                "storage_key": object_name,
                "file_hash": None,
                "upload_status": "completed",
            },
        )

        if old_storage_key and old_storage_key != object_name:
            try:
                old_storage.delete_object(old_storage_key)
            except Exception:
                pass

        AssetService._parse_asset_sync(db, asset_id, force=True)
        return AssetDAO.get_asset_by_id(db, asset_id).to_dict()

    @staticmethod
    def _upload_asset_common(
        db: Session,
        file: UploadFile,
        type: int,
        title: Optional[str] = None,
        source_type: int = 0,
        is_internal: bool = False,
        user_id: int | None = None,
        is_skip_analysis: bool = False,
    ) -> dict:
        ext = AssetService._validate_file(file, type)
        object_name = AssetService.generate_object_name(asset_type=type, ext=ext, is_internal=is_internal)
        file_url = AssetService._upload_fileobj(file.file, object_name, file.content_type)

        final_title = AssetService._normalize_title(
            title,
            file.filename or f"{AssetService.TYPE_NAME.get(type, 'asset')}_{uuid.uuid4().hex[:8]}",
        )
        asset = AssetDAO.create_asset(
            db,
            {
                "type": type,
                "title": final_title,
                "url": file_url,
                "file_size": getattr(file, "size", None),
                "duration": None,
                "format": ext,
                "ai_features": None,
                "source_type": source_type,
                "user_id": AssetService._library_owner_id(user_id),
                "storage_key": object_name,
                "upload_status": "completed",
                "scope": {"type": "library"},
            },
        )
        if is_skip_analysis:
            return asset.to_dict()
        if type in [1, 2]:
            AssetService._parse_asset_sync(db, asset.id, force=True)
            refreshed = AssetDAO.get_asset_by_id(db, asset.id)
            return refreshed.to_dict()
        return asset.to_dict()

    @staticmethod
    async def upload_user_asset(
        db: Session,
        background_tasks: BackgroundTasks,
        file: UploadFile,
        type: int,
        title: Optional[str] = None,
        source_type: int = 0,
        skip_analysis: bool = False,
        user_id: int = 0,
    ) -> dict:
        asset_dict = AssetService._upload_asset_common(
            db=db,
            file=file,
            type=type,
            title=title,
            source_type=source_type,
            is_internal=False,
            user_id=user_id,
            is_skip_analysis=skip_analysis,
        )
        return {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "unknown"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "file_size": asset_dict["file_size"],
            "duration": asset_dict["duration"],
            "format": asset_dict["format"],
            "ai_features": asset_dict["ai_features"],
            "source_type": asset_dict["source_type"],
            "created_at": asset_dict["created_at"],
            "analysis_performed": not skip_analysis,
        }

    @staticmethod
    async def upload_internal_asset(
        db: Session,
        file: UploadFile,
        type: int,
        title: Optional[str] = None,
        source_type: int = 1,
        skip_ai_analysis: bool = True,
        user_id: int = 0,
    ) -> dict:
        asset_dict = AssetService._upload_asset_common(
            db=db,
            file=file,
            type=type,
            title=title,
            source_type=source_type,
            is_internal=True,
            user_id=user_id,
            is_skip_analysis=skip_ai_analysis,
        )
        return {
            "id": asset_dict["id"],
            "type": asset_dict["type"],
            "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "unknown"),
            "title": asset_dict["title"],
            "url": asset_dict["url"],
            "file_size": asset_dict["file_size"],
            "duration": asset_dict["duration"],
            "format": asset_dict["format"],
            "ai_features": asset_dict["ai_features"],
            "source_type": asset_dict["source_type"],
            "created_at": asset_dict["created_at"],
        }

    @staticmethod
    def list_assets(
        db: Session,
        user_id: Optional[int],
        type: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
        format: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if type is not None and type not in [1, 2, 3, 4]:
            raise BusinessException(PARAM_ERROR, "invalid asset type")

        total, results = AssetDAO.list_assets(
            db=db,
            user_id=AssetService._library_owner_id(user_id),
            type=type,
            source_type=source_type,
            keyword=keyword,
            format=format,
            scope="library",
            page=page,
            page_size=page_size,
        )
        asset_list = []
        for asset, username in results:
            asset_dict = asset.to_dict()
            # 转换解析状态为数字
            status_map = {
                "pending": 0,
                "running": 1,
                "completed": 2,
                "failed": 3
            }
            status = status_map.get(asset_dict.get("parsing_status"), 0)

            # 转换文件大小为可读格式
            size = asset_dict.get("file_size")
            if size:
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            else:
                size_str = "未知"

            asset_list.append(
                {
                    "id": asset_dict["id"],
                    "type": asset_dict["type"],
                    "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "unknown"),
                    "title": asset_dict["title"],
                    "url": asset_dict["url"],
                    "size": size_str,
                    "duration": asset_dict["duration"],
                    "format": asset_dict["format"],
                    "ai_features": asset_dict["ai_features"],
                    "content_text": asset_dict.get("content_text"),
                    "source_type": asset_dict["source_type"],
                    "createdAt": asset_dict["created_at"],
                    "username": username or "未知用户",
                    "status": status,
                    "parsing_status": asset_dict.get("parsing_status")
                }
            )
        return {
            "list": asset_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    @staticmethod
    def get_asset_detail(db: Session, user_id: Optional[int], asset_id: int) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        # 权限校验：只有所有者或管理员可以操作
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")
        return asset.to_dict()

    @staticmethod
    def update_asset(db: Session, user_id: Optional[int], asset_id: int, title: Optional[str] = None, ai_features: Optional[dict] = None) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        # 权限校验：只有所有者或管理员可以操作
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")

        update_data = {}
        if title is not None:
            final_title = title.strip()
            if not final_title:
                raise BusinessException(PARAM_ERROR, "asset title cannot be empty")
            update_data["title"] = final_title
        if ai_features is not None:
            if not isinstance(ai_features, dict):
                raise BusinessException(PARAM_ERROR, "ai_features must be an object")
            update_data["ai_features"] = ai_features
        if not update_data:
            return asset.to_dict()
        updated_asset = AssetDAO.update_asset(db, asset_id, update_data)
        return updated_asset.to_dict()

    @staticmethod
    async def parse_asset(db: Session, user_id: Optional[int], asset_id: int, force: bool = False, product_id: Optional[int] = None) -> dict:
        """触发资产解析，使用BaseParsingService的通用逻辑"""
        from backend.v1.app.product.dao.product_dao import ProductDAO

        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        # 权限校验：只有所有者或管理员可以操作
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")

        # 如果提供了product_id，验证产品是否存在
        if product_id:
            product = ProductDAO.get_product_by_id(db, product_id)
            if not product:
                raise BusinessException(PARAM_ERROR, "product not found")

        # 调用基类的触发解析方法
        service = AssetService()
        context = {"asset_type": asset.type}
        if product_id:
            context["product_id"] = product_id  # 将product_id传入上下文，供流水线使用
        success = service.trigger_parsing(db, asset_id, force=force, context=context)

        if not success:
            # 获取最新的资产状态
            updated_asset = AssetDAO.get_asset_by_id(db, asset_id)
            if updated_asset.parsing_status == "failed":
                raise BusinessException(PARAM_ERROR, f"解析失败: {updated_asset.parsing_error}")

        # 获取最新的资产信息
        updated_asset = AssetDAO.get_asset_by_id(db, asset_id)

        # 如果提供了product_id，建立资产和产品的关联
        if product_id:
            from backend.v1.app.product.dao.product_dao import ProductDAO
            # 检查是否已经关联
            existing_association = db.execute(
                text("SELECT 1 FROM product_assets WHERE product_id = :product_id AND asset_id = :asset_id AND role = :role"),
                {"product_id": product_id, "asset_id": asset_id, "role": "image" if updated_asset.type == 1 else "video" if updated_asset.type == 2 else "audio"}
            ).first()

            if not existing_association:
                # 创建新的关联
                db.execute(
                    text("INSERT INTO product_assets (product_id, asset_id, role) VALUES (:product_id, :asset_id, :role)"),
                    {"product_id": product_id, "asset_id": asset_id, "role": "image" if updated_asset.type == 1 else "video" if updated_asset.type == 2 else "audio"}
                )
                db.commit()

        return {
            "id": updated_asset.id,
            "type": updated_asset.type,
            "type_name": AssetService.TYPE_NAME.get(updated_asset.type, "unknown"),
            "title": updated_asset.title,
            "url": updated_asset.url,
            "duration": updated_asset.duration,
            "ai_features": updated_asset.ai_features,
            "parsing_status": updated_asset.parsing_status,
            "execution_id": updated_asset.execution_id,
            "parsing_error": updated_asset.parsing_error,
            "analysis_completed": updated_asset.parsing_status == "completed",
            "product_id": product_id if product_id else None
        }

    @staticmethod
    def get_parsing_progress(db: Session, user_id: Optional[int], asset_id: int) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        # 权限校验：只有所有者或管理员可以操作
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")
        return {
            "asset_id": asset.id,
            "parsing_status": asset.parsing_status,
            "execution_id": asset.execution_id,
            "parsing_error": asset.parsing_error,
            "updated_at": asset.updated_at.isoformat() + "Z" if asset.updated_at else None,
        }

    @staticmethod
    async def retry_parsing(db: Session, user_id: Optional[int], asset_id: int, product_id: Optional[int] = None) -> dict:
        return await AssetService.parse_asset(db=db, user_id=user_id, asset_id=asset_id, force=True, product_id=product_id)

    @staticmethod
    def _parse_asset_sync(db: Session, asset_id: int, force: bool = False, product_id: Optional[int] = None, user_id: Optional[int] = None):
        """
        同步解析资产，保持原有接口兼容
        内部使用新的ProductParsingPipeline实现
        """
        from backend.v1.app.product.dao.product_dao import ProductDAO

        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type not in [1, 2, 4]:
            raise BusinessException(PARAM_ERROR, "asset type does not support parsing")
        if asset.parsing_status == "completed" and not force and asset.ai_features:
            return asset
        # 权限校验：如果提供了user_id则校验所有者
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")

        # 如果提供了product_id，验证产品是否存在
        if product_id:
            product = ProductDAO.get_product_by_id(db, product_id)
            if not product:
                raise BusinessException(PARAM_ERROR, "product not found")

        # 更新状态为pending
        AssetDAO.update_asset(db, asset_id, {"parsing_status": "pending", "parsing_error": None})
        asset = AssetDAO.get_asset_by_id(db, asset_id)

        try:
            # 创建商品解析流水线
            pipeline = PipelineFactory.get_product_pipeline(
                enable_persistence=True,
                persist_to_asset=True
            )

            # 构建流水线参数
            object_name = AssetService.get_path_after_baseurl(asset.url)
            pipeline_params = {
                "asset_id": asset_id,
                "asset_url": asset.url,
                "object_name": object_name,
                "asset_type": asset.type
            }

            # 如果有product_id，添加到参数中
            if product_id:
                pipeline_params["product_id"] = product_id

            # 根据资产类型自动添加对应字段
            if asset.type == 1:  # 图片
                pipeline_params["images"] = [asset.url]
            elif asset.type == 2:  # 视频
                pipeline_params["video_url"] = asset.url
                pipeline_params["video_object_name"] = object_name  # 传入视频对象存储路径
                pipeline_params["video_duration"] = asset.duration  # 传入视频时长

            # 执行流水线（同步调用）
            pipeline_result = pipeline.run_with_persistence(pipeline_params)

            if not pipeline_result.get("success", False):
                error_msg = f"解析失败: {pipeline_result.get('errors', [])}"
                AssetDAO.update_asset(db, asset_id, {
                    "parsing_status": "failed",
                    "parsing_error": error_msg
                })
                raise BusinessException(PARAM_ERROR, error_msg)

            # 流水线执行成功，更新状态为running（异步执行）
            update_data = {"parsing_status": "running"}
            if "execution_id" in pipeline_result:
                update_data["execution_id"] = pipeline_result["execution_id"]

            AssetDAO.update_asset(db, asset_id, update_data)

            # 如果提供了product_id，建立资产和产品的关联
            if product_id:
                # 检查是否已经关联
                existing_association = db.execute(
                    text("SELECT 1 FROM product_assets WHERE product_id = :product_id AND asset_id = :asset_id AND role = :role"),
                    {"product_id": product_id, "asset_id": asset_id, "role": "image" if asset.type == 1 else "video" if asset.type == 2 else "audio"}
                ).first()

                if not existing_association:
                    # 创建新的关联
                    db.execute(
                        text("INSERT INTO product_assets (product_id, asset_id, role) VALUES (:product_id, :asset_id, :role)"),
                        {"product_id": product_id, "asset_id": asset_id, "role": "image" if asset.type == 1 else "video" if asset.type == 2 else "audio"}
                    )
                    db.commit()

            # 返回最新的资产信息
            return AssetDAO.get_asset_by_id(db, asset_id)

        except Exception as exc:
            error_msg = str(exc)
            AssetDAO.update_asset(db, asset_id, {
                "parsing_status": "failed",
                "parsing_error": error_msg
            })
            raise BusinessException(PARAM_ERROR, f"解析失败: {error_msg}")

    @staticmethod
    def delete_asset(db: Session, user_id: Optional[int], asset_id: int) -> None:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        # 权限校验：只有所有者或管理员可以操作
        if user_id is not None and asset.user_id != user_id:
            from backend.framework.exceptions.error_codes import FORBIDDEN
            raise BusinessException(FORBIDDEN, "无权限操作此资产")
        if asset.storage_key:
            storage = AssetService._storage_for_asset_url(asset.url)
            try:
                storage.delete_object(asset.storage_key)
            except Exception:
                pass
        success = AssetDAO.delete_asset(db, asset_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "delete failed")

    @staticmethod
    def get_path_after_baseurl(url: str, baseurl: str = "https://vidmuse.tos-cn-beijing.volces.com") -> str:
        if not url:
            return ""
        if url.startswith(baseurl):
            return url[len(baseurl):].lstrip("/")
        parsed = urlparse(url)
        return parsed.path.lstrip("/")
