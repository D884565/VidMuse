# backend/v1/app/push/dto/message_schema.py
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime

class PushMessageBase(BaseModel):
    """推送消息基础模型"""
    message_id: str = Field(description="消息唯一ID")
    message_type: str = Field(description="消息类型")
    title: str = Field(description="消息标题")
    content: Any = Field(description="消息内容")
    level: str = Field(default="info", description="消息级别")
    trace_id: Optional[str] = Field(None, description="关联的trace_id")
    extra: Optional[dict] = Field(None, description="扩展字段")
    created_at: datetime = Field(description="创建时间")

    model_config = {
        "from_attributes": True
    }

class PushMessageCreate(BaseModel):
    """消息创建模型（内部使用）"""
    message_type: str = Field(description="消息类型")
    title: str = Field(description="消息标题")
    content: Any = Field(description="消息内容")
    level: str = Field(default="info", description="消息级别")
    trace_id: Optional[str] = Field(None, description="关联的trace_id")
    user_id: int = Field(description="接收用户ID")
    extra: Optional[dict] = Field(None, description="扩展字段")

class UserMessageResponse(PushMessageBase):
    """用户消息响应模型"""
    is_read: bool = Field(description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")

class MessageListResponse(BaseModel):
    """消息列表响应"""
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    unread_count: int = Field(description="未读消息总数")
    list: List[UserMessageResponse] = Field(description="消息列表")

class MessageQueryRequest(BaseModel):
    """消息查询请求"""
    message_type: Optional[str] = Field(None, description="按消息类型筛选")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    is_read: Optional[bool] = Field(None, description="按已读状态筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")

class MarkReadRequest(BaseModel):
    """标记已读请求"""
    message_ids: List[str] = Field(description="要标记为已读的消息ID列表")
