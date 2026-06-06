from typing import Optional

from backend.store.obj.base import ObjectStorage
from backend.store.obj.local_client import get_local_storage_client
from backend.store.obj.minio_client import get_minio_client
from backend.store.obj.tos_client import get_tos_client
from backend.v1.app.config.config import settings


class StorageType:
    MINIO = "minio"
    TOS = "tos"
    LOCAL = "local"


def get_storage_client(storage_type: Optional[str] = None) -> ObjectStorage:
    if storage_type is None:
        storage_type = getattr(settings, "STORAGE_TYPE", StorageType.MINIO)

    if storage_type == StorageType.MINIO:
        return get_minio_client()
    if storage_type == StorageType.TOS:
        return get_tos_client()
    if storage_type == StorageType.LOCAL:
        return get_local_storage_client()
    raise ValueError(f"Unsupported storage type: {storage_type}")
