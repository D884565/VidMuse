"""共享认证依赖

提供 JWT 认证的 FastAPI 依赖，供所有控制器复用。
"""
from typing import Optional
from fastapi import Header, Depends
from sqlalchemy.orm import Session

from backend.v1.app.user.service.user_service import UserService
from backend.store.database.sync_database import get_db
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import UNAUTHORIZED, FORBIDDEN


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """从 Authorization 请求头解析当前登录用户的ID

    用法：在路由函数参数中通过 Depends(get_current_user_id) 注入。
    请求头格式：Authorization: Bearer <access_token>

    :param authorization: Authorization 请求头的值
    :return: 当前用户ID
    :raises BusinessException: 未携带 token 或 token 无效时抛出 UNAUTHORIZED
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessException(UNAUTHORIZED)
    token = authorization[7:]
    return UserService.get_user_id_from_token(token)


def admin_required(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> int:
    """管理员权限校验依赖，要求当前用户是超级管理员

    用法：在路由函数参数中通过 Depends(admin_required) 注入。
    只有角色为0的超级管理员可以访问。

    :param current_user_id: 当前登录用户ID
    :param db: 数据库会话
    :return: 当前管理员用户ID
    :raises BusinessException: 没有管理员权限时抛出 FORBIDDEN
    """
    user = UserService.get_user_info(db, current_user_id)
    # 角色：0-超级管理员, 1-普通用户, 2-VIP用户
    if user.get("role") != 0:
        raise BusinessException(FORBIDDEN, message="需要管理员权限")
    return current_user_id
