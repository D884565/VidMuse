from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Optional, BinaryIO


class ObjectStorage(ABC):
    """对象存储抽象基类"""

    @abstractmethod
    def upload_file(self, file_path: str, object_name: str, content_type: Optional[str] = None) -> str:
        """
        上传本地文件到对象存储
        :param file_path: 本地文件路径
        :param object_name: 对象存储中的文件名
        :param content_type: 文件内容类型
        :return: 文件访问URL
        """
        pass

    @abstractmethod
    def upload_fileobj(self, file: BinaryIO, object_name: str, content_type: Optional[str] = None) -> str:
        """
        上传文件对象到对象存储
        :param file: 文件对象
        :param object_name: 对象存储中的文件名
        :param content_type: 文件内容类型
        :return: 文件访问URL
        """
        pass

    @abstractmethod
    def download_file(self, object_name: str, file_path: str) -> None:
        """
        从对象存储下载文件到本地
        :param object_name: 对象存储中的文件名
        :param file_path: 本地保存路径
        """
        pass

    @abstractmethod
    def get_object(self, object_name: str) -> bytes:
        """
        获取对象内容
        :param object_name: 对象存储中的文件名
        :return: 对象内容字节
        """
        pass

    @abstractmethod
    def delete_object(self, object_name: str) -> None:
        """
        删除对象
        :param object_name: 对象存储中的文件名
        """
        pass

    @abstractmethod
    def get_presigned_url(self, object_name: str, expires_in: timedelta = timedelta(hours=1)) -> str:
        """
        获取对象的预签名访问URL
        :param object_name: 对象存储中的文件名
        :param expires_in: 过期时间
        :return: 预签名URL
        """
        pass


    @abstractmethod
    def object_exists(self, object_name: str) -> bool:
        """
        检查对象是否存在
        :param object_name: 对象存储中的文件名
        :return: 是否存在
        """
        pass

    @abstractmethod
    def get_bucket_name(self) -> str:
        """
        获取存储桶名称
        :return: 存储桶名称
        """
        pass

