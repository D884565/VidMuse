"""共享认证依赖

提供 JWT 认证的 FastAPI 依赖，供所有控制器复用。
"""
from typing import Optional
from fastapi import Header

from backend.v1.app.user.service.user_service import UserService


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """从 Authorization 请求头解析当前登录用户的ID

    用法：在路由函数参数中通过 Depends(get_current_user_id) 注入。
    请求头格式：Authorization: Bearer <access_token>

    :param authorization: Authorization 请求头的值
    :return: 当前用户ID
    :raises BusinessException: 未携带 token 或 token 无效时抛出 UNAUTHORIZED
    """
    if not authorization or not authorization.startswith("Bearer "):
        from backend.framework.exceptions.exceptions import BusinessException
        from backend.framework.exceptions.error_codes import UNAUTHORIZED
        raise BusinessException(UNAUTHORIZED)
    token = authorization[7:]
    return UserService.get_user_id_from_token(token)
