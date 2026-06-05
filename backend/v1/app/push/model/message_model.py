# backend/v1/app/push/model/message_model.py
from sqlalchemy import Column, BigInteger, String, Text, JSON, DateTime, Integer, Boolean
from sqlalchemy.sql import func

from backend.store.database.async_database import Base


class PushMessage(Base):
    """推送消息表"""
    __tablename__ = "push_messages"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    message_id = Column(String(36), unique=True, index=True, nullable=False, comment="消息唯一ID")
    message_type = Column(String(50), index=True, nullable=False, comment="消息类型")
    title = Column(String(255), nullable=False, comment="消息标题")
    content = Column(JSON, nullable=False, comment="消息内容")
    level = Column(String(20), default="info", comment="消息级别：info/success/warning/error")
    trace_id = Column(String(64), index=True, comment="关联的trace_id")
    extra = Column(JSON, comment="扩展字段")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

class UserMessage(Base):
    """用户消息关联表"""
    __tablename__ = "user_messages"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    message_id = Column(String(36), index=True, nullable=False, comment="消息ID")
    is_read = Column(Boolean, default=False, comment="是否已读")
    read_at = Column(DateTime(timezone=True), comment="阅读时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    __table_args__ = (
        {"comment": "用户消息关联表"},
    )
