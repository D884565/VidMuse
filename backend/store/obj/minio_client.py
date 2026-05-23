from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from backend.v1.app.config.config import settings
from backend.store.obj.base import ObjectStorage


class MinioClient(ObjectStorage):
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

    def download_file(self, object_name: str, file_path: str) -> None:
        """从MinIO下载文件到本地"""
        try:
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path
            )
        except S3Error as e:
            raise RuntimeError(f"从MinIO下载文件失败: {str(e)}")

    def get_object(self, object_name: str) -> bytes:
        """获取对象内容"""
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return response.read()
        except S3Error as e:
            raise RuntimeError(f"获取MinIO对象失败: {str(e)}")
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()

    def delete_object(self, object_name: str) -> None:
        """删除对象"""
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
        except S3Error as e:
            raise RuntimeError(f"删除MinIO对象失败: {str(e)}")

    def get_presigned_upload_url(self, object_name: str, expires_in: timedelta = timedelta(hours=1),
                                content_type: Optional[str] = None) -> str:
        """获取预签名上传URL"""
        try:
            return self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires_in
            )
        except S3Error as e:
            raise RuntimeError(f"获取MinIO预签名上传URL失败: {str(e)}")

    def object_exists(self, object_name: str) -> bool:
        """检查对象是否存在"""
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            raise RuntimeError(f"检查MinIO对象是否存在失败: {str(e)}")


def get_minio_client() -> MinioClient:
    """获取MinIO客户端实例"""
    return MinioClient()
