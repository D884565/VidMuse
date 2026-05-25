"""用户模型"""
import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class User(Base):
    """用户表 ORM 模型"""
    __tablename__ = "users"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 基本信息
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希（bcrypt）")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="头像URL")

    # 角色
    role: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="角色 0=管理员 1=普通用户 2=VIP")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系：用户拥有多个商品
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
