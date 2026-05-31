"""用户业务逻辑层

职责：处理用户相关的业务逻辑，包括注册、登录、JWT 令牌管理、密码哈希等。
不直接操作数据库，通过 UserDAO 访问数据层。
"""
import jwt
import datetime
from typing import Optional
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.v1.app.config.config import settings
from backend.v1.app.models.user import User
from backend.v1.app.user.dao.user_dao import UserDAO
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import (
    USER_NOT_FOUND,
    USER_ALREADY_EXISTS,
    USERNAME_OR_PASSWORD_ERROR,
    PASSWORD_ERROR,
    ACCOUNT_DISABLED,
    LOGIN_EXPIRED,
    UNAUTHORIZED,
)

# 密码哈希上下文，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 角色ID -> 角色名称映射
ROLE_NAME_MAP = {0: "超级管理员", 1: "普通用户", 2: "VIP用户"}


class UserService:
    """用户业务逻辑层"""

    # ==================== 密码工具方法 ====================

    @staticmethod
    def _hash_password(password: str) -> str:
        """将明文密码哈希为 bcrypt 摘要

        bcrypt 算法限制密码最长为 72 字节，超出部分需要截断
        """
        # bcrypt 限制密码不能超过 72 字节
        # 先编码为 UTF-8 检查长度
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            # 截断到 72 字节，然后安全解码回字符串
            password = password_bytes[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(password)

    @staticmethod
    def _verify_password(plain: str, hashed: str) -> bool:
        """验证明文密码是否匹配哈希值

        验证时也需要对密码进行相同的截断处理
        """
        # bcrypt 限制密码不能超过 72 字节
        # 先编码为 UTF-8 检查长度
        plain_bytes = plain.encode('utf-8')
        if len(plain_bytes) > 72:
            # 截断到 72 字节，然后安全解码回字符串
            plain = plain_bytes[:72].decode('utf-8', errors='ignore')
        return pwd_context.verify(plain, hashed)

    # ==================== JWT 令牌方法 ====================

    @staticmethod
    def _create_token(user_id: int, username: str, role: int) -> dict:
        """生成 access_token 和 refresh_token

        :param user_id: 用户ID
        :param username: 用户名
        :param role: 用户角色
        :return: 包含 token 信息的字典
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        # access_token：有效期2小时
        expire = now + datetime.timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS)
        payload = {
            "sub": str(user_id),    # 标准 subject 字段存用户ID
            "username": username,
            "role": role,
            "exp": expire,
            "iat": now,
        }
        access_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # refresh_token：有效期7天
        refresh_payload = {
            "sub": str(user_id),
            "type": "refresh",      # 标记为刷新令牌，与 access_token 区分
            "exp": now + datetime.timedelta(days=7),
            "iat": now,
        }
        refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS,
        }

    # ==================== 业务方法 ====================

    @staticmethod
    def register(db: Session, username: str, password: str, avatar_url: Optional[str] = None) -> dict:
        """用户注册

        :param db: 数据库会话
        :param username: 用户名
        :param password: 明文密码
        :param avatar_url: 头像URL（可选）
        :return: Token 信息字典
        :raises BusinessException: 用户名已存在时抛出 USER_ALREADY_EXISTS
        """
        # 检查用户名是否已存在
        existing = UserDAO.get_user_by_username(db, username)
        if existing:
            raise BusinessException(USER_ALREADY_EXISTS)

        # 创建用户记录
        user_data = {
            "username": username,
            "password_hash": password,
            "avatar_url": avatar_url,
            "role": 1,      # 默认普通用户
        }
        user = UserDAO.create_user(db, user_data)

        # 生成 Token 并返回
        token_data = UserService._create_token(user.id, user.username, user.role)
        token_data["created_at"] = user.created_at.isoformat() if user.created_at else ""
        return token_data

    @staticmethod
    def login(db: Session, username: str, password: str) -> dict:
        """用户登录

        :param db: 数据库会话
        :param username: 用户名
        :param password: 明文密码
        :return: Token 信息字典
        :raises BusinessException: 用户不存在、密码错误、账号被禁用时抛出对应异常
        """
        # 查找用户
        user = UserDAO.get_user_by_username(db, username)
        if not user:
            raise BusinessException(USERNAME_OR_PASSWORD_ERROR)

        # 检查账号状态（init.sql 中无 status 字段，暂不检查）
        # if user.status == 0:
        #     raise BusinessException(ACCOUNT_DISABLED)

        # 验证密码
        if password != user.password_hash:
            raise BusinessException(USERNAME_OR_PASSWORD_ERROR)

        return UserService._create_token(user.id, user.username, user.role)

    @staticmethod
    def refresh_token(db: Session, refresh_token: str) -> dict:
        """使用 refresh_token 获取新的 access_token

        :param db: 数据库会话
        :param refresh_token: 刷新令牌
        :return: 新的 access_token 信息
        :raises BusinessException: token 过期或无效时抛出异常
        """
        try:
            payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise BusinessException(LOGIN_EXPIRED)
        except jwt.InvalidTokenError:
            raise BusinessException(UNAUTHORIZED)

        # 验证 token 类型必须是 refresh
        if payload.get("type") != "refresh":
            raise BusinessException(UNAUTHORIZED)

        # 查询用户是否存在
        user_id = int(payload["sub"])
        user = UserDAO.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(USER_NOT_FOUND)

        # 生成新的 access_token
        now = datetime.datetime.now(datetime.timezone.utc)
        expire = now + datetime.timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS)
        new_payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": expire,
            "iat": now,
        }
        access_token = jwt.encode(new_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return {
            "access_token": access_token,
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS,
        }

    @staticmethod
    def get_user_info(db: Session, user_id: int) -> dict:
        """获取用户详细信息

        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户信息字典
        :raises BusinessException: 用户不存在时抛出 USER_NOT_FOUND
        """
        user = UserDAO.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(USER_NOT_FOUND)
        return {
            "id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "role_name": ROLE_NAME_MAP.get(user.role, "未知"),
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "updated_at": user.updated_at.isoformat() if user.updated_at else "",
        }

    @staticmethod
    def update_user(db: Session, user_id: int, username: Optional[str] = None, avatar_url: Optional[str] = None) -> dict:
        """更新用户信息

        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param username: 新用户名（可选）
        :param avatar_url: 新头像URL（可选）
        :return: 更新后的用户信息
        :raises BusinessException: 用户不存在或用户名已存在时抛出异常
        """
        user = UserDAO.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(USER_NOT_FOUND)

        update_data = {}

        # 如果要修改用户名，先检查是否已被占用
        if username is not None:
            existing = UserDAO.get_user_by_username(db, username)
            if existing and existing.id != user_id:
                raise BusinessException(USER_ALREADY_EXISTS)
            update_data["username"] = username

        if avatar_url is not None:
            update_data["avatar_url"] = avatar_url

        # 执行更新
        if update_data:
            user = UserDAO.update_user(db, user_id, update_data)

        return {
            "id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "updated_at": user.updated_at.isoformat() if user.updated_at else "",
        }

    @staticmethod
    def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> None:
        """修改密码

        :param db: 数据库会话
        :param user_id: 用户ID
        :param old_password: 原密码
        :param new_password: 新密码
        :raises BusinessException: 用户不存在或原密码错误时抛出异常
        """
        user = UserDAO.get_user_by_id(db, user_id)
        if not user:
            raise BusinessException(USER_NOT_FOUND)

        # 验证原密码
        if not UserService._verify_password(old_password, user.password_hash):
            raise BusinessException(PASSWORD_ERROR)

        # 更新为新密码的哈希值
        UserDAO.update_user(db, user_id, {"password_hash": UserService._hash_password(new_password)})

    @staticmethod
    def list_users(db: Session, role: Optional[int] = None, keyword: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
        """获取用户列表（管理员接口）

        :param db: 数据库会话
        :param role: 按角色筛选（可选）
        :param keyword: 按用户名搜索（可选）
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果字典
        """
        total, users = UserDAO.list_users(db, role=role, keyword=keyword, page=page, page_size=page_size)
        user_list = []
        for u in users:
            user_list.append({
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "role_name": ROLE_NAME_MAP.get(u.role, "未知"),
                "created_at": u.created_at.isoformat() if u.created_at else "",
            })
        return {
            "list": user_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }

    @staticmethod
    def get_user_id_from_token(token: str) -> int:
        """从 JWT token 中解析用户ID

        用于 Controller 层的认证依赖注入，从 Header 中的 Bearer token 解析当前用户。

        :param token: JWT access_token
        :return: 用户ID
        :raises BusinessException: token 过期或无效时抛出异常
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return int(payload["sub"])
        except jwt.ExpiredSignatureError:
            raise BusinessException(LOGIN_EXPIRED)
        except jwt.InvalidTokenError:
            raise BusinessException(UNAUTHORIZED)


# 模块级单例，Controller 层直接引用
user_service = UserService()
