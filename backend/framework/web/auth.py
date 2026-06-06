"""共享认证依赖

提供 JWT 认证的 FastAPI 依赖，供所有控制器复用。
"""
from typing import Optional, Dict, Any
from fastapi import Header, Depends
import jwt

from backend.v1.app.user.service.user_service import UserService
from backend.v1.app.config.config import settings
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import UNAUTHORIZED, FORBIDDEN, LOGIN_EXPIRED


from typing import Annotated, Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 定义 security scheme，Swagger 会显示 Authorize 按钮
security = HTTPBearer(auto_error=False)  # auto_error=False 允许我们自己处理 401


def parse_token_payload(token: str) -> Dict[str, Any]:
    """解析JWT token，返回完整的payload信息"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise BusinessException(LOGIN_EXPIRED)
    except jwt.InvalidTokenError:
        raise BusinessException(UNAUTHORIZED)


def parse_token_from_header(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    """从Authorization头中解析token，返回完整payload"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return parse_token_payload(token)


def get_current_user_id(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> int:
    """
    从 Authorization 请求头解析当前登录用户的ID
    现在通过 HTTPBearer 对接 Swagger Authorize 按钮
    """
    if not credentials:
        raise BusinessException(UNAUTHORIZED)

    payload = parse_token_payload(credentials.credentials)
    user_id = int(payload["sub"])

    if not user_id:
        raise BusinessException(UNAUTHORIZED)
    return user_id


def get_current_user_payload(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> Dict[str, Any]:
    """
    从 Authorization 请求头解析当前登录用户的完整payload信息
    包含user_id, username, role等信息，无需查询数据库
    """
    if not credentials:
        raise BusinessException(UNAUTHORIZED)

    payload = parse_token_payload(credentials.credentials)

    if not payload.get("sub"):
        raise BusinessException(UNAUTHORIZED)

    return payload


def admin_required(
    payload: Annotated[Dict[str, Any], Depends(get_current_user_payload)]
) -> int:
    """
    管理员权限校验依赖
    直接从JWT payload中获取角色信息，无需查询数据库，性能更高且兼容异步接口
    """
    user_role = payload.get("role")
    if user_role != 0:
        raise BusinessException(FORBIDDEN, message="需要管理员权限")
    return int(payload["sub"])
