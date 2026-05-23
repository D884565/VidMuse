from typing import Optional, Any
from backend.framework.exceptions.error_codes import (
    SYSTEM_ERROR,
    BUSINESS_ERROR,
    PARAM_ERROR,
    UNAUTHORIZED,
    FORBIDDEN,
    RESOURCE_NOT_FOUND,
    RESOURCE_CONFLICT,
    REQUEST_TOO_FREQUENT
)


class BaseAppException(Exception):
    """应用基础异常类"""
    code: str = SYSTEM_ERROR[0]
    message: str = SYSTEM_ERROR[1]
    data: Optional[Any] = None

    def __init__(self, *args, data: Optional[Any] = None, **kwargs):
        # 支持两种调用方式：
        # 1. 传入错误码元组：BaseAppException(ERROR_CODE, data=xxx)
        # 2. 传统方式：BaseAppException(message="xxx", code="xxx", data=xxx)
        if args and len(args) >= 1:
            first_arg = args[0]
            if isinstance(first_arg, tuple) and len(first_arg) == 2:
                # 错误码元组格式：(code, message)
                self.code = first_arg[0]
                self.message = first_arg[1]
                # 如果有第二个参数，作为message的补充
                if len(args) >= 2 and isinstance(args[1], str):
                    self.message = args[1]
            elif isinstance(first_arg, str):
                # 第一个参数是message
                self.message = first_arg
                if len(args) >= 2:
                    self.code = args[1]

        # 关键字参数优先级更高
        if 'message' in kwargs:
            self.message = kwargs['message']
        if 'code' in kwargs:
            self.code = kwargs['code']
        if data is not None:
            self.data = data

        super().__init__(self.message)


class BusinessException(BaseAppException):
    """业务异常"""
    code: str = BUSINESS_ERROR[0]
    message: str = BUSINESS_ERROR[1]


class ValidationException(BaseAppException):
    """参数验证异常"""
    code: str = PARAM_ERROR[0]
    message: str = PARAM_ERROR[1]


class UnauthorizedException(BaseAppException):
    """未授权异常"""
    code: str = UNAUTHORIZED[0]
    message: str = UNAUTHORIZED[1]


class ForbiddenException(BaseAppException):
    """禁止访问异常"""
    code: str = FORBIDDEN[0]
    message: str = FORBIDDEN[1]


class NotFoundException(BaseAppException):
    """资源不存在异常"""
    code: str = RESOURCE_NOT_FOUND[0]
    message: str = RESOURCE_NOT_FOUND[1]


class ConflictException(BaseAppException):
    """资源冲突异常"""
    code: str = RESOURCE_CONFLICT[0]
    message: str = RESOURCE_CONFLICT[1]


class RateLimitException(BaseAppException):
    """限流异常"""
    code: str = REQUEST_TOO_FREQUENT[0]
    message: str = REQUEST_TOO_FREQUENT[1]
