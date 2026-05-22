import time
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from backend.app.core.config import settings


class MinioClient:
    """MinIO 客户端封装"""
    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化客户端（仅执行一次）"""
        if self._initialized:
            return
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()
        self._initialized = True

    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                        }
                    ]
                }
                self.client.set_bucket_policy(self.bucket_name, policy)
        except S3Error as e:
            raise RuntimeError(f"初始化MinIO存储桶失败: {str(e)}")

    def upload_file(self, file_path: str, object_name: str, content_type: str = None) -> str:
        """上传文件到MinIO"""
        try:
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type
            )
            protocol = "https" if settings.MINIO_SECURE else "http"
            return f"{protocol}://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
        except S3Error as e:
            raise RuntimeError(f"上传文件到MinIO失败: {str(e)}")

    def upload_fileobj(self, file, object_name: str, content_type: str = None) -> str:
        """上传文件对象到MinIO"""
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type=content_type,
            )
            protocol = "https" if settings.MINIO_SECURE else "http"
            return f"{protocol}://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
        except S3Error as e:
            raise RuntimeError(f"上传文件对象到MinIO失败: {str(e)}")

    def get_presigned_url(self, object_name: str, expires_in: timedelta = timedelta(hours=1)) -> str:
        """获取预签名URL"""
        try:
            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires_in
            )
        except S3Error as e:
            raise RuntimeError(f"获取预签名URL失败: {str(e)}")


def get_minio_client() -> MinioClient:
    """获取MinIO客户端实例"""
    return MinioClient()
