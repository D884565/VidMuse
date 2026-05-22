"""MinIO 文件操作服务"""
import os
from minio import Minio
from backend.app.core.config import settings
from backend.app.core.minio_client import get_minio_client


class MinioService:
    """MinIO 文件上传下载"""

    def __init__(self):
        self.client: Minio = get_minio_client()
        self.bucket = settings.MINIO_BUCKET_NAME

    def upload_file(self, local_path: str, object_name: str) -> str:
        """
        上传文件到 MinIO。
        :param local_path: 本地文件路径
        :param object_name: MinIO 对象路径，如 projects/1/output.mp4
        :returns: 可访问的 URL
        """
        self.client.fput_object(self.bucket, object_name, local_path)
        return f"{self.bucket}/{object_name}"

    def download_file(self, object_name: str, local_path: str):
        """从 MinIO 下载文件到本地"""
        self.client.fget_object(self.bucket, object_name, local_path)

    def get_url(self, object_name: str) -> str:
        """获取文件访问路径"""
        return f"{self.bucket}/{object_name}"

    def delete_file(self, object_name: str):
        """删除文件"""
        self.client.remove_object(self.bucket, object_name)


minio_service = MinioService()
