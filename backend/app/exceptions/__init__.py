# 异常和错误码包
# 统一导出所有异常类、错误码和异常处理器

from backend.app.exceptions.exceptions import (
    BaseAppException,
    BusinessException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    RateLimitException
)
from backend.app.exceptions.exception_handler import register_exception_handlers
from backend.app.exceptions.error_codes import *

__all__ = [
    # 异常类
    'BaseAppException',
    'BusinessException',
    'ValidationException',
    'UnauthorizedException',
    'ForbiddenException',
    'NotFoundException',
    'ConflictException',
    'RateLimitException',
    # 异常处理器
    'register_exception_handlers',
]
