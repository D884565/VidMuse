"""MinIO 客户端初始化"""
from minio import Minio
from backend.app.core.config import settings


def get_minio_client() -> Minio:
    """获取 MinIO 客户端实例"""
    client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    # 确保 bucket 存在
    bucket = settings.MINIO_BUCKET_NAME
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    return client
