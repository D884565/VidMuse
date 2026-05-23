"""
对象存储模块
提供统一的对象存储访问接口，支持多种存储后端
"""

from backend.store.obj.base import ObjectStorage
from backend.store.obj.tos_client import TOSClient, get_tos_client
from backend.store.obj.factory import get_storage_client, StorageType

__all__ = [
    "ObjectStorage",
    "TOSClient",
    "get_tos_client",
    "get_storage_client",
    "StorageType"
]
