import time
from datetime import timedelta
from logging import Logger
from typing import Optional, BinaryIO, Any

import requests
import tos
from tos import HttpMethodType
from tos.exceptions import TosServerError, TosClientError

from backend.v1.app.config.config import settings
from backend.framework.exceptions.exceptions import BaseAppException
from backend.framework.exceptions.error_codes import THIRD_PARTY_TIMEOUT, OSS_ERROR
from .base import ObjectStorage

logger = Logger(__name__)

# 上传重试配置
_UPLOAD_MAX_RETRIES = 5
_UPLOAD_RETRY_BACKOFF = [3, 8, 15, 25, 40]  # 秒，渐进退避


class TOSClient(ObjectStorage):
    """火山引擎对象存储 TOS 客户端封装"""
    _instance = None
    _initialized = False

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化客户端（仅执行一次）"""
        if self._initialized:
            return

        if not settings.TOS_ENDPOINT or not settings.TOS_ACCESS_KEY or not settings.TOS_SECRET_KEY or not settings.TOS_BUCKET_NAME:
            raise RuntimeError("TOS 配置不完整，请检查配置项 TOS_ENDPOINT, TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_BUCKET_NAME")

        self.client = tos.TosClientV2(
            endpoint=settings.TOS_ENDPOINT,
            ak=settings.TOS_ACCESS_KEY,
            sk=settings.TOS_SECRET_KEY,
            region=settings.TOS_REGION
        )
        self.bucket_name = settings.TOS_BUCKET_NAME
        self._ensure_bucket_exists()
        self._initialized = True

    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        try:
            self.client.head_bucket(self.bucket_name)
        except TosServerError as e:
            if e.status_code == 404:
                # 存储桶不存在，创建存储桶
                self.client.create_bucket(self.bucket_name)
                # 设置公共读权限
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["tos:GetObject"],
                            "Resource": [f"tos:::{self.bucket_name}/*"]
                        }
                    ]
                }
                self.client.put_bucket_policy(self.bucket_name, str(policy))
            else:
                raise RuntimeError(f"检查TOS存储桶失败: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"初始化TOS存储桶失败: {str(e)}") from e

    def upload_file(self, file_path: str, object_name: str, content_type: Optional[str] = None) -> str | None:
        """上传文件到TOS，带重试机制"""
        last_exc = None
        for attempt in range(_UPLOAD_MAX_RETRIES + 1):
            try:
                with open(file_path, 'rb') as f:
                    self.client.put_object(
                        bucket=self.bucket_name,
                        key=object_name,
                        content=f,
                        content_type=content_type
                    )

                protocol = "https" if settings.TOS_SECURE else "http"
                url = f"{protocol}://{self.bucket_name}.{settings.TOS_ENDPOINT}/{object_name}"

                # 设置对象ACL为公共读
                try:
                    self.client.put_object_acl(
                        bucket=self.bucket_name,
                        key=object_name,
                        acl=tos.ACLType.ACL_Public_Read
                    )
                except Exception:
                    pass  # ACL设置失败不影响上传

                return url
            except (TosServerError, TosClientError, TimeoutError, ConnectionError, OSError) as e:
                last_exc = e
                is_retryable = self._is_retryable_error(e)
                if is_retryable and attempt < _UPLOAD_MAX_RETRIES:
                    delay = _UPLOAD_RETRY_BACKOFF[attempt] if attempt < len(_UPLOAD_RETRY_BACKOFF) else _UPLOAD_RETRY_BACKOFF[-1]
                    logger.warning(
                        f"[TOS] 上传失败 (attempt {attempt + 1}/{_UPLOAD_MAX_RETRIES + 1}), "
                        f"{delay}s 后重试: {e}"
                    )
                    time.sleep(delay)
                    continue
                # 不可重试或已用完重试次数
                if isinstance(e, (TosServerError, TosClientError)):
                    self._handle_tos_error(e)
                raise BaseAppException(OSS_ERROR, message=f"上传文件到TOS失败: {str(e)}") from e
            except Exception as e:
                raise BaseAppException(OSS_ERROR, message=f"上传文件到TOS失败: {str(e)}") from e
        # 理论上不会到这里，但保险起见
        raise BaseAppException(OSS_ERROR, message=f"上传文件到TOS失败（已重试{_UPLOAD_MAX_RETRIES}次）: {last_exc}")

    def upload_fileobj(self, file: BinaryIO, object_name: str, content_type: Optional[str] = None) -> str | None:
        """上传文件对象到TOS"""
        try:
            self.client.put_object(
                bucket=self.bucket_name,
                key=object_name,
                content=file,
                content_type=content_type
            )

            protocol = "https" if settings.TOS_SECURE else "http"
            url = f"{protocol}://{self.bucket_name}.{settings.TOS_ENDPOINT}/{object_name}"

            # 设置对象ACL为公共读
            try:
                self.client.put_object_acl(
                    bucket=self.bucket_name,
                    key=object_name,
                    acl=tos.ACLType.ACL_Public_Read
                )
            except Exception:
                pass

            return url
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"上传文件对象到TOS失败: {str(e)}") from e

    def download_file(self, object_name: str, file_path: str) -> None:
        """从TOS下载文件到本地"""
        try:
            resp = self.client.get_object(
                bucket=self.bucket_name,
                key=object_name
            )

            with open(file_path, 'wb') as f:
                for chunk in resp:
                    f.write(chunk)
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"从TOS下载文件失败: {str(e)}") from e

    def get_object(self, object_name: str) -> Any | None:
        """获取对象内容"""
        try:
            resp = self.client.get_object(
                bucket=self.bucket_name,
                key=object_name
            )
            return resp.read()
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"获取TOS对象失败: {str(e)}") from e

    def delete_object(self, object_name: str) -> None:
        """删除对象"""
        try:
            self.client.delete_object(
                bucket=self.bucket_name,
                key=object_name
            )
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"删除TOS对象失败: {str(e)}") from e

    def get_presigned_url(self, object_name: str, expires_in: timedelta = timedelta(hours=1)) -> Any | None:
        """获取预签名URL"""
        try:
            expires_seconds = int(expires_in.total_seconds())
            url = self.client.pre_signed_url(
                bucket=self.bucket_name,
                key=object_name,
                expires=expires_seconds,
                http_method=HttpMethodType.Http_Method_Put
            )
            return url.signed_url
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"获取TOS预签名URL失败: {str(e)}") from e


    def object_exists(self, object_name: str) -> bool | None:
        """检查对象是否存在"""
        try:
            self.client.head_object(
                bucket=self.bucket_name,
                key=object_name
            )
            return True
        except TosServerError as e:
            if e.status_code == 404:
                return False
            raise
        except (TosServerError, TosClientError) as e:
            self._handle_tos_error(e)
        except Exception as e:
            raise BaseAppException(OSS_ERROR, message=f"检查TOS对象是否存在失败: {str(e)}") from e

    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        """判断是否为可重试的瞬时错误（宽松模式）"""
        err_str = str(e).lower()
        # 超时、连接中断、网络错误、DNS错误等
        retryable_keywords = [
            "timeout", "timed out", "connection", "abort", "eof",
            "broken pipe", "reset", "refused", "unreachable",
            "temporary", "retry", "busy", "throttl", "rate limit",
            "503", "502", "500", "429"
        ]
        if any(kw in err_str for kw in retryable_keywords):
            return True
        if isinstance(e, (TimeoutError, ConnectionError, OSError)):
            return True
        # TOS 4xx/5xx 服务端错误都可重试（除了 404）
        if isinstance(e, TosServerError):
            return e.status_code != 404
        # TosClientError 也可重试
        if isinstance(e, TosClientError):
            return True
        return False

    def _handle_tos_error(self, e: Exception):
        """处理TOS相关错误"""
        if isinstance(e, TosClientError):
            if "timeout" in str(e).lower():
                raise BaseAppException(THIRD_PARTY_TIMEOUT, message=f"TOS服务调用超时: {str(e)}") from e
            raise BaseAppException(OSS_ERROR, message=f"TOS客户端错误: {str(e)}") from e
        elif isinstance(e, TosServerError):
            raise BaseAppException(OSS_ERROR, message=f"TOS服务端错误: {str(e)} (状态码: {e.status_code})") from e
        else:
            raise BaseAppException(OSS_ERROR, message=f"TOS未知错误: {str(e)}") from e

    def get_bucket_name(self) -> str:
        return self.bucket_name


def get_tos_client() -> TOSClient:
    """获取TOS客户端实例"""
    return TOSClient()
