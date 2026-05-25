"""用户模块 Pydantic 模型

定义用户模块的请求体和响应体结构，用于 FastAPI 的参数校验和序列化。
"""
from typing import Optional
from pydantic import BaseModel, Field


# ==================== 请求模型 ====================

class UserRegisterRequest(BaseModel):
    """注册请求体"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名，2-50字符")
    password: str = Field(..., min_length=8, max_length=32, description="密码，8-32字符，需包含字母和数字")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserLoginRequest(BaseModel):
    """登录请求体"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserUpdateRequest(BaseModel):
    """更新用户信息请求体"""
    username: Optional[str] = Field(None, min_length=2, max_length=50, description="新用户名")
    avatar_url: Optional[str] = Field(None, description="新头像URL")


class PasswordChangeRequest(BaseModel):
    """修改密码请求体"""
    old_password: str = Field(..., description="原密码")
    new_password: str = Field(..., min_length=8, max_length=32, description="新密码")


# ==================== 响应模型 ====================

class UserResponse(BaseModel):
    """用户信息响应体"""
    id: int
    username: str
    avatar_url: Optional[str] = None
    role: int
    role_name: str = ""  # 角色中文名，由 Service 层填充
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}  # 支持从 ORM 对象直接转换


class TokenResponse(BaseModel):
    """登录/注册成功后的 Token 响应体"""
    user_id: int
    username: str
    role: int
    access_token: str      # JWT 访问令牌，有效期2小时
    refresh_token: str     # JWT 刷新令牌，有效期7天
    expires_in: int         # access_token 过期时间（秒）
