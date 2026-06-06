from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class PushMessageBase(BaseModel):
    """Base push message response."""

    message_id: str = Field(description="消息唯一ID")
    message_type: str = Field(description="消息类型")
    title: str = Field(description="消息标题")
    content: Any = Field(description="消息内容")
    level: str = Field(default="info", description="消息级别")
    trace_id: Optional[str] = Field(None, description="关联 trace_id")
    business_type: Optional[str] = Field(None, description="业务类型")
    task_id: Optional[str] = Field(None, description="任务ID")
    task_domain: Optional[str] = Field(None, description="任务域")
    task_type: Optional[str] = Field(None, description="任务类型")
    project_id: Optional[int] = Field(None, description="项目ID")
    asset_id: Optional[int] = Field(None, description="素材ID")
    event_type: Optional[str] = Field(None, description="任务事件类型")
    status: Optional[str] = Field(None, description="任务状态")
    progress: Optional[int] = Field(None, description="任务进度")
    extra: Optional[dict] = Field(None, description="扩展字段")
    created_at: datetime = Field(description="创建时间")

    model_config = {
        "from_attributes": True
    }


class PushMessageCreate(BaseModel):
    """Internal push message create model."""

    message_type: str = Field(description="消息类型")
    title: str = Field(description="消息标题")
    content: Any = Field(description="消息内容")
    level: str = Field(default="info", description="消息级别")
    trace_id: Optional[str] = Field(None, description="关联 trace_id")
    user_id: int = Field(description="接收用户ID")
    business_type: Optional[str] = Field(None, description="业务类型")
    task_id: Optional[str] = Field(None, description="任务ID")
    task_domain: Optional[str] = Field(None, description="任务域")
    task_type: Optional[str] = Field(None, description="任务类型")
    project_id: Optional[int] = Field(None, description="项目ID")
    asset_id: Optional[int] = Field(None, description="素材ID")
    event_type: Optional[str] = Field(None, description="任务事件类型")
    status: Optional[str] = Field(None, description="任务状态")
    progress: Optional[int] = Field(None, description="任务进度")
    extra: Optional[dict] = Field(None, description="扩展字段")


class UserMessageResponse(PushMessageBase):
    """User push message response."""

    is_read: bool = Field(description="是否已读")
    read_at: Optional[datetime] = Field(None, description="阅读时间")


class MessageListResponse(BaseModel):
    """Paginated message list response."""

    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    unread_count: int = Field(description="未读消息总数")
    list: List[UserMessageResponse] = Field(description="消息列表")


class MessageQueryRequest(BaseModel):
    """Message query request."""

    message_type: Optional[str] = Field(None, description="按消息类型筛选")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    is_read: Optional[bool] = Field(None, description="按已读状态筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class MarkReadRequest(BaseModel):
    """Mark messages as read request."""

    message_ids: List[str] = Field(description="要标记为已读的消息ID列表")
