import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from backend.framework.exceptions.error_codes import PARAM_ERROR
from backend.framework.exceptions.exceptions import BusinessException
from backend.store import get_storage_client
from backend.store.obj.local_client import get_local_storage_client
from backend.v1.app.assets.service.asset_analysis_orchestrator import AssetAnalysisOrchestrator
from backend.v1.app.assets.core.upload_bitmap import UploadBitmapStore
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.assets.dao.asset_upload_session_dao import AssetUploadSessionDAO
from backend.v1.app.config.config import settings


class AssetService:
    TYPE_NAME = {
        1: "image",
        2: "video",
        3: "audio",
        4: "text",
    }

    _bitmap_store = UploadBitmapStore()
    _analysis_orchestrator = AssetAnalysisOrchestrator()

    @staticmethod
    def _library_owner_id() -> Optional[int]:
        return None

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
    def _chunk_path(temp_dir: str, chunk_index: int) -> str:
        return os.path.join(temp_dir, f"chunk_{chunk_index:06d}.part")

    @staticmethod
    def _merged_file_path(temp_dir: str, file_name: str) -> str:
        return os.path.join(temp_dir, f"merged_{file_name}")

    @staticmethod
    def _upload_file_with_fallback(file_path: str, object_name: str, content_type: Optional[str] = None) -> str:
        try:
            return get_storage_client().upload_file(file_path, object_name, content_type)
        except Exception:
            return get_local_storage_client().upload_file(file_path, object_name, content_type)

    @staticmethod
    def _upload_fileobj_with_fallback(file_obj, object_name: str, content_type: Optional[str] = None) -> str:
        try:
            stream = getattr(file_obj, "file", file_obj)
            if hasattr(stream, "seek"):
                stream.seek(0)
            return get_storage_client().upload_fileobj(stream, object_name, content_type)
        except Exception:
            stream = getattr(file_obj, "file", file_obj)
            if hasattr(stream, "seek"):
                stream.seek(0)
            return get_local_storage_client().upload_fileobj(stream, object_name, content_type)

    @staticmethod
    def _storage_for_asset_url(url: Optional[str]):
        if url and url.startswith(settings.LOCAL_STORAGE_URL_PREFIX):
            return get_local_storage_client()
        return get_storage_client()

    @staticmethod
    def _build_session_response(session) -> dict:
        uploaded_indexes = AssetService._bitmap_store.get_uploaded_indexes(
            session.redis_bitmap_key,
            session.total_chunks,
        )
        return {
            "session_id": session.session_id,
            "asset_id": session.asset_id,
            "chunk_size": session.chunk_size,
            "total_chunks": session.total_chunks,
            "upload_status": session.status,
            "uploaded_chunks": len(uploaded_indexes),
            "uploaded_indexes": uploaded_indexes,
        }

    @staticmethod
    def create_text_asset(db: Session, title: Optional[str], content_text: str) -> dict:
        content = (content_text or "").strip()
        if not content:
            raise BusinessException(PARAM_ERROR, "text content cannot be empty")

        final_title = AssetService._normalize_title(title, "Untitled text asset")
        asset = AssetDAO.create_asset(
            db,
            {
                "user_id": AssetService._library_owner_id(),
                "type": 4,
                "title": final_title,
                "url": "",
                "file_size": None,
                "duration": None,
                "format": "text",
                "ai_features": None,
                "content_text": content,
                "source_type": 0,
                "scope": "library",
            },
        )
        AssetService._parse_asset_sync(db, asset.id, force=True)
        return AssetDAO.get_asset_by_id(db, asset.id).to_dict()

    @staticmethod
    def update_text_asset(db: Session, asset_id: int, title: Optional[str], content_text: str) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type != 4:
            raise BusinessException(PARAM_ERROR, "only text assets can be edited here")

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
    def init_resumable_upload(
        db: Session,
        file_name: str,
        file_size: int,
        chunk_size: int,
        file_hash: str,
    ) -> dict:
        if file_size <= 0 or chunk_size <= 0:
            raise BusinessException(PARAM_ERROR, "file_size and chunk_size must be positive")

        existing = AssetUploadSessionDAO.find_active_session(
            db,
            asset_id=None,
            mode="create",
            file_hash=file_hash,
            chunk_size=chunk_size,
        )
        if existing:
            return AssetService._build_session_response(existing)

        session_id = uuid.uuid4().hex
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        redis_bitmap_key = f"asset:upload:bitmap:{session_id}"
        temp_dir = os.path.join(AssetService._default_upload_root(), session_id)
        os.makedirs(temp_dir, exist_ok=True)

        session = AssetUploadSessionDAO.create_session(
            db,
            {
                "session_id": session_id,
                "asset_id": None,
                "mode": "create",
                "file_name": file_name,
                "file_hash": file_hash,
                "file_size": file_size,
                "chunk_size": chunk_size,
                "total_chunks": total_chunks,
                "uploaded_chunks": 0,
                "status": "pending",
                "redis_bitmap_key": redis_bitmap_key,
                "temp_dir": temp_dir,
                "expires_at": None,
            },
        )
        return AssetService._build_session_response(session)

    @staticmethod
    async def upload_image_chunk(
        db: Session,
        session_id: str,
        chunk_index: int,
        chunk: UploadFile,
    ) -> dict:
        session = AssetUploadSessionDAO.get_by_session_id(db, session_id)
        if not session:
            raise BusinessException(PARAM_ERROR, "upload session not found")
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise BusinessException(PARAM_ERROR, "chunk index out of range")

        os.makedirs(session.temp_dir, exist_ok=True)
        chunk_path = AssetService._chunk_path(session.temp_dir, chunk_index)
        with open(chunk_path, "wb") as fh:
            fh.write(await chunk.read())

        AssetService._bitmap_store.set_bit(session.redis_bitmap_key, chunk_index)
        uploaded_indexes = AssetService._bitmap_store.get_uploaded_indexes(session.redis_bitmap_key, session.total_chunks)
        status = "completed" if len(uploaded_indexes) == session.total_chunks else "uploading"
        updated_session = AssetUploadSessionDAO.update_session(
            db,
            session_id,
            {
                "uploaded_chunks": len(uploaded_indexes),
                "status": status,
            },
        )
        return {
            "session_id": session_id,
            "chunk_index": chunk_index,
            "uploaded": True,
            "uploaded_chunks": updated_session.uploaded_chunks if updated_session else len(uploaded_indexes),
            "total_chunks": session.total_chunks,
        }

    @staticmethod
    def get_upload_status(db: Session, session_id: str) -> dict:
        session = AssetUploadSessionDAO.get_by_session_id(db, session_id)
        if not session:
            raise BusinessException(PARAM_ERROR, "upload session not found")
        return AssetService._build_session_response(session)

    @staticmethod
    def _merge_chunks(session) -> str:
        uploaded_indexes = AssetService._bitmap_store.get_uploaded_indexes(session.redis_bitmap_key, session.total_chunks)
        if len(uploaded_indexes) != session.total_chunks:
            raise BusinessException(PARAM_ERROR, "upload is incomplete")

        merged_path = AssetService._merged_file_path(session.temp_dir, session.file_name)
        with open(merged_path, "wb") as merged:
            for chunk_index in range(session.total_chunks):
                chunk_path = AssetService._chunk_path(session.temp_dir, chunk_index)
                if not os.path.exists(chunk_path):
                    raise BusinessException(PARAM_ERROR, "chunk file missing")
                with open(chunk_path, "rb") as chunk_file:
                    shutil.copyfileobj(chunk_file, merged)
        return merged_path

    @staticmethod
    def _cleanup_session_files(session) -> None:
        AssetService._bitmap_store.clear(session.redis_bitmap_key)
        shutil.rmtree(session.temp_dir, ignore_errors=True)

    @staticmethod
    def complete_resumable_upload(db: Session, session_id: str, title: Optional[str] = None) -> dict:
        session = AssetUploadSessionDAO.get_by_session_id(db, session_id)
        if not session:
            raise BusinessException(PARAM_ERROR, "upload session not found")

        merged_path = AssetService._merge_chunks(session)
        ext = Path(session.file_name).suffix.lstrip(".").lower() or "bin"
        object_name = AssetService.generate_object_name(asset_type=1, ext=ext)
        file_url = AssetService._upload_file_with_fallback(merged_path, object_name)
        final_title = AssetService._normalize_title(title, session.file_name)

        asset = AssetDAO.create_asset(
            db,
            {
                "user_id": AssetService._library_owner_id(),
                "type": 1,
                "title": final_title,
                "url": file_url,
                "file_size": session.file_size,
                "duration": None,
                "format": ext,
                "ai_features": None,
                "source_type": 0,
                "storage_key": object_name,
                "file_hash": session.file_hash,
                "upload_status": "completed",
                "upload_session_id": session.session_id,
                "chunk_size": session.chunk_size,
                "total_chunks": session.total_chunks,
                "scope": "library",
            },
        )
        AssetUploadSessionDAO.update_session(db, session_id, {"status": "completed", "asset_id": asset.id})
        AssetService._cleanup_session_files(session)
        AssetService._parse_asset_sync(db, asset.id, force=True)
        return AssetDAO.get_asset_by_id(db, asset.id).to_dict()

    @staticmethod
    def init_image_reupload(
        db: Session,
        asset_id: int,
        file_name: str,
        file_size: int,
        chunk_size: int,
        file_hash: str,
    ) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type != 1:
            raise BusinessException(PARAM_ERROR, "only image assets support reupload")
        if file_size <= 0 or chunk_size <= 0:
            raise BusinessException(PARAM_ERROR, "file_size and chunk_size must be positive")

        existing = AssetUploadSessionDAO.find_active_session(
            db,
            asset_id=asset_id,
            mode="replace",
            file_hash=file_hash,
            chunk_size=chunk_size,
        )
        if existing:
            return AssetService._build_session_response(existing)

        session_id = uuid.uuid4().hex
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        temp_dir = os.path.join(AssetService._default_upload_root(), session_id)
        os.makedirs(temp_dir, exist_ok=True)

        session = AssetUploadSessionDAO.create_session(
            db,
            {
                "session_id": session_id,
                "asset_id": asset_id,
                "mode": "replace",
                "file_name": file_name,
                "file_hash": file_hash,
                "file_size": file_size,
                "chunk_size": chunk_size,
                "total_chunks": total_chunks,
                "uploaded_chunks": 0,
                "status": "pending",
                "redis_bitmap_key": f"asset:upload:bitmap:{session_id}",
                "temp_dir": temp_dir,
                "expires_at": None,
            },
        )
        return AssetService._build_session_response(session)

    @staticmethod
    def complete_image_reupload(
        db: Session,
        asset_id: int,
        session_id: str,
        title: Optional[str] = None,
    ) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")

        session = AssetUploadSessionDAO.get_by_session_id(db, session_id)
        if not session:
            raise BusinessException(PARAM_ERROR, "upload session not found")

        old_storage_key = asset.storage_key
        merged_path = AssetService._merge_chunks(session)
        ext = Path(session.file_name).suffix.lstrip(".").lower() or "bin"
        object_name = AssetService.generate_object_name(asset_type=1, ext=ext)
        file_url = AssetService._upload_file_with_fallback(merged_path, object_name)

        update_data = {
            "title": AssetService._normalize_title(title, asset.title or session.file_name),
            "url": file_url,
            "storage_key": object_name,
            "file_hash": session.file_hash,
            "file_size": session.file_size,
            "format": ext,
            "upload_status": "completed",
            "upload_session_id": session.session_id,
            "chunk_size": session.chunk_size,
            "total_chunks": session.total_chunks,
        }
        updated_asset = AssetDAO.update_asset(db, asset_id, update_data)
        AssetUploadSessionDAO.update_session(db, session_id, {"status": "completed"})

        if old_storage_key and old_storage_key != object_name:
            storage = AssetService._storage_for_asset_url(asset.url)
            try:
                storage.delete_object(old_storage_key)
            except Exception:
                pass

        AssetService._cleanup_session_files(session)
        AssetService._parse_asset_sync(db, asset_id, force=True)
        return AssetDAO.get_asset_by_id(db, asset_id).to_dict()

    @staticmethod
    async def reupload_image_asset(
        db: Session,
        asset_id: int,
        file: UploadFile,
        title: Optional[str] = None,
    ) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type != 1:
            raise BusinessException(PARAM_ERROR, "only image assets support reupload")

        ext = AssetService._validate_file(file, 1)
        object_name = AssetService.generate_object_name(asset_type=1, ext=ext)
        file_url = AssetService._upload_fileobj_with_fallback(file.file, object_name, file.content_type)

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
                "upload_session_id": None,
                "chunk_size": None,
                "total_chunks": None,
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
    ) -> dict:
        ext = AssetService._validate_file(file, type)
        object_name = AssetService.generate_object_name(asset_type=type, ext=ext, is_internal=is_internal)
        file_url = AssetService._upload_fileobj_with_fallback(file.file, object_name, file.content_type)

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
                "user_id": user_id,
                "storage_key": object_name,
                "upload_status": "completed",
                "scope": "library",
            },
        )
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
    ) -> dict:
        asset_dict = AssetService._upload_asset_common(
            db=db,
            file=file,
            type=type,
            title=title,
            source_type=source_type,
            is_internal=False,
            user_id=AssetService._library_owner_id(),
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
    ) -> dict:
        asset_dict = AssetService._upload_asset_common(
            db=db,
            file=file,
            type=type,
            title=title,
            source_type=source_type,
            is_internal=True,
            user_id=None,
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
        type: Optional[int] = None,
        source_type: Optional[int] = None,
        keyword: Optional[str] = None,
        format: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if type is not None and type not in [1, 2, 3, 4]:
            raise BusinessException(PARAM_ERROR, "invalid asset type")

        total, assets = AssetDAO.list_assets(
            db=db,
            user_id=AssetService._library_owner_id(),
            type=type,
            source_type=source_type,
            keyword=keyword,
            format=format,
            scope="library",
            page=page,
            page_size=page_size,
        )
        asset_list = []
        for asset in assets:
            asset_dict = asset.to_dict()
            asset_list.append(
                {
                    "id": asset_dict["id"],
                    "type": asset_dict["type"],
                    "type_name": AssetService.TYPE_NAME.get(asset_dict["type"], "unknown"),
                    "title": asset_dict["title"],
                    "url": asset_dict["url"],
                    "file_size": asset_dict["file_size"],
                    "duration": asset_dict["duration"],
                    "format": asset_dict["format"],
                    "ai_features": asset_dict["ai_features"],
                    "content_text": asset_dict.get("content_text"),
                    "source_type": asset_dict["source_type"],
                    "created_at": asset_dict["created_at"],
                }
            )
        return {
            "list": asset_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            },
        }

    @staticmethod
    def get_asset_detail(db: Session, asset_id: int) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        return asset.to_dict()

    @staticmethod
    def update_asset(db: Session, asset_id: int, title: Optional[str] = None, ai_features: Optional[dict] = None) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")

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
    async def parse_asset(db: Session, asset_id: int, force: bool = False) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        updated_asset = AssetService._parse_asset_sync(db, asset_id, force=force)
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
        }

    @staticmethod
    def get_parsing_progress(db: Session, asset_id: int) -> dict:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        return {
            "asset_id": asset.id,
            "parsing_status": asset.parsing_status,
            "execution_id": asset.execution_id,
            "parsing_error": asset.parsing_error,
            "updated_at": asset.updated_at.isoformat() + "Z" if asset.updated_at else None,
        }

    @staticmethod
    async def retry_parsing(db: Session, asset_id: int) -> dict:
        return await AssetService.parse_asset(db=db, asset_id=asset_id, force=True)

    @staticmethod
    def _parse_asset_sync(db: Session, asset_id: int, force: bool = False):
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
        if asset.type not in [1, 2, 4]:
            raise BusinessException(PARAM_ERROR, "asset type does not support parsing")
        if asset.parsing_status == "completed" and not force and asset.ai_features:
            return asset

        AssetDAO.update_asset(db, asset_id, {"parsing_status": "running", "parsing_error": None})
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        try:
            ai_features = AssetService._analysis_orchestrator.analyze_asset(asset)
            return AssetDAO.update_asset(
                db,
                asset_id,
                {
                    "ai_features": ai_features,
                    "parsing_status": "completed",
                    "parsing_error": None,
                },
            )
        except Exception as exc:
            AssetDAO.update_asset(
                db,
                asset_id,
                {
                    "parsing_status": "failed",
                    "parsing_error": str(exc),
                },
            )
            raise

    @staticmethod
    def delete_asset(db: Session, asset_id: int) -> None:
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, "asset not found")
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
