from datetime import timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from backend.store.obj.base import ObjectStorage
from backend.v1.app.config.config import settings


class LocalFileStorage(ObjectStorage):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.root = Path(settings.LOCAL_STORAGE_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    def _resolve_path(self, object_name: str) -> Path:
        target = self.root / Path(object_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _build_url(self, object_name: str) -> str:
        normalized = object_name.replace("\\", "/")
        return f"{settings.LOCAL_STORAGE_URL_PREFIX}/{quote(normalized)}"

    def upload_file(self, file_path: str, object_name: str, content_type: Optional[str] = None) -> str:
        target = self._resolve_path(object_name)
        target.write_bytes(Path(file_path).read_bytes())
        return self._build_url(object_name)

    def upload_fileobj(self, file, object_name: str, content_type: Optional[str] = None) -> str:
        target = self._resolve_path(object_name)
        stream = getattr(file, "file", file)
        if hasattr(stream, "seek"):
            stream.seek(0)
        with target.open("wb") as output:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        return self._build_url(object_name)

    def download_file(self, object_name: str, file_path: str) -> None:
        Path(file_path).write_bytes(self._resolve_path(object_name).read_bytes())

    def get_object(self, object_name: str) -> bytes:
        return self._resolve_path(object_name).read_bytes()

    def delete_object(self, object_name: str) -> None:
        target = self._resolve_path(object_name)
        if target.exists():
            target.unlink()

    def get_presigned_url(self, object_name: str, expires_in: timedelta = timedelta(hours=1)) -> str:
        return self._build_url(object_name)

    def object_exists(self, object_name: str) -> bool:
        return self._resolve_path(object_name).exists()

    def get_bucket_name(self) -> str:
        return "local"


def get_local_storage_client() -> LocalFileStorage:
    return LocalFileStorage()
