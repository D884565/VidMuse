from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from backend.framework.errorcode import SUCCESS, SYSTEM_ERROR

T = TypeVar('T')


class Response(BaseModel, Generic[T]):
    """统一响应格式
    遵循阿里巴巴开发守则，code为7位字符串错误码
    """
    code: str
    message: str
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Optional[T] = None, message: Optional[str] = None, code: Optional[str] = None) -> "Response[T]":
        """成功响应
        默认使用 SUCCESS 错误码: 0000000
        """
        if code is None:
            code = SUCCESS[0]
        if message is None:
            message = SUCCESS[1]
        return cls(code=code, message=message, data=data)

    @classmethod
    def error(cls, code: Optional[str] = None, message: Optional[str] = None, data: Optional[T] = None) -> "Response[T]":
        """错误响应
        默认使用 SYSTEM_ERROR 错误码: B000001
        """
        if code is None:
            code = SYSTEM_ERROR[0]
        if message is None:
            message = SYSTEM_ERROR[1]
        return cls(code=code, message=message, data=data)
