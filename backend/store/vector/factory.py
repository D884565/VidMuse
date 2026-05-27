from typing import Optional

from backend.v1.app.config.config import settings
from .base import VectorDatabase
from .chromadb_client import get_chromadb_client
from .milvus_client import get_milvus_client


class VectorDBType:
    """向量数据库类型枚举"""
    CHROMADB = "chromadb"
    MILVUS = "milvus"


def get_vector_db_client(db_type: Optional[str] = None) -> VectorDatabase:
    """
    获取向量数据库客户端实例
    :param db_type: 向量数据库类型，默认从配置中读取
    :return: 向量数据库客户端实例
    """
    if db_type is None:
        db_type = getattr(settings, "VECTOR_DB_TYPE", VectorDBType.CHROMADB)

    if db_type == VectorDBType.CHROMADB:
        return get_chromadb_client()
    elif db_type == VectorDBType.MILVUS:
        return get_milvus_client()
    else:
        raise ValueError(f"不支持的向量数据库类型: {db_type}")
