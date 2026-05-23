from typing import Optional

from backend.v1.app.config.config import settings
from .base import ObjectStorage
from .tos_client import get_tos_client
from backend.store.obj.minio_client import get_minio_client


class StorageType:
    """存储类型枚举"""
    MINIO = "minio"
    TOS = "tos"


def get_storage_client(storage_type: Optional[str] = None) -> ObjectStorage:
    """
    获取存储客户端实例
    :param storage_type: 存储类型，默认从配置中读取
    :return: 存储客户端实例
    """
    if storage_type is None:
        storage_type = getattr(settings, "STORAGE_TYPE", StorageType.MINIO)

    if storage_type == StorageType.MINIO:
        return get_minio_client()
    elif storage_type == StorageType.TOS:
        return get_tos_client()
    else:
        raise ValueError(f"不支持的存储类型: {storage_type}")
