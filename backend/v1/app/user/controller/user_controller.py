"""用户路由

职责：定义用户模块的 HTTP 接口，处理请求参数解析和响应包装。
所有业务逻辑委托给 UserService，自身不包含业务代码。
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.framework.web.auth import get_current_user_id
from backend.store.database.sync_database import get_db
from backend.v1.app.user.service.user_service import user_service
from backend.v1.app.user.dao.schema import (
    UserRegisterRequest,
    UserLoginRequest,
    UserUpdateRequest,
    PasswordChangeRequest,
)

router = APIRouter(tags=["用户模块"])


# ==================== 认证接口（无需登录） ====================

@router.post("/auth/register", response_model=Response, summary="用户注册")
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """新用户注册账号，成功后直接返回 Token"""
    result = user_service.register(db, req.username, req.password, req.avatar_url)
    return Response.success(data=result, message="注册成功")


@router.post("/auth/login", response_model=Response, summary="用户登录")
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """账号密码登录，返回 access_token 和 refresh_token"""
    result = user_service.login(db, req.username, req.password)
    return Response.success(data=result, message="登录成功")


@router.post("/auth/refresh", response_model=Response, summary="刷新Token")
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    """使用 refresh_token 获取新的 access_token"""
    result = user_service.refresh_token(db, refresh_token)
    return Response.success(data=result, message="刷新成功")


@router.post("/auth/logout", response_model=Response, summary="退出登录")
def logout(current_user_id: int = Depends(get_current_user_id)):
    """退出登录（JWT 无状态，客户端丢弃 token 即可）"""
    return Response.success(data=None, message="退出成功")


# ==================== 用户信息接口（需要登录） ====================

@router.get("/users/me", response_model=Response, summary="获取当前用户信息")
def get_me(current_user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """获取当前登录用户的详细信息"""
    result = user_service.get_user_info(db, current_user_id)
    return Response.success(data=result)


@router.put("/users/me", response_model=Response, summary="更新用户信息")
def update_me(req: UserUpdateRequest, current_user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """更新当前用户的用户名和头像"""
    result = user_service.update_user(db, current_user_id, req.username, req.avatar_url)
    return Response.success(data=result, message="更新成功")


@router.put("/users/me/password", response_model=Response, summary="修改密码")
def change_password(req: PasswordChangeRequest, current_user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """修改当前用户的密码"""
    user_service.change_password(db, current_user_id, req.old_password, req.new_password)
    return Response.success(data=None, message="密码修改成功")


# ==================== 管理员接口 ====================

@router.get("/users", response_model=Response, summary="获取用户列表（管理员）")
def list_users(
    role: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取所有用户列表，支持按角色筛选和关键词搜索"""
    result = user_service.list_users(db, role=role, keyword=keyword, page=page, page_size=page_size)
    return Response.success(data=result)
