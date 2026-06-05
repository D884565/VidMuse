# backend/v1/app/push/controller/message_controller.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from backend.framework.web.auth import get_current_user_id
from backend.framework.web.response import Response
from backend.store.database.async_database import get_db

from ..dto.message_schema import (
    MessageListResponse,
    MessageQueryRequest,
    MarkReadRequest,
    UserMessageResponse
)
from ..dao.message_dao import message_dao
from ..service.push_service import push_service

router = APIRouter(prefix="/messages", tags=["消息管理"])


@router.get("", response_model=Response[MessageListResponse])
def get_user_messages(
    message_type: Optional[str] = Query(None, description="按消息类型筛选"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    is_read: Optional[bool] = Query(None, description="按已读状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """查询当前用户的消息列表"""
    query_params = MessageQueryRequest(
        message_type=message_type,
        start_time=start_time,
        end_time=end_time,
        is_read=is_read,
        page=page,
        page_size=page_size
    )

    total, unread_count, messages = message_dao.get_user_messages(db, current_user.id, query_params)

    return Response.success(data=MessageListResponse(
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
        list=[UserMessageResponse.from_orm(msg) for msg in messages]
    ))


@router.post("/read", response_model=Response)
def mark_messages_as_read(
    request: MarkReadRequest,
    current_user = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """批量标记消息为已读"""
    updated = message_dao.mark_messages_as_read(db, current_user.id, request.message_ids)
    return Response.success(data={"updated_count": updated})


@router.get("/unread-count", response_model=Response)
def get_unread_count(
    current_user = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取当前用户未读消息数量"""
    count = message_dao.get_unread_count(db, current_user.id)
    return Response.success(data={"unread_count": count})


@router.post("/test-push", response_model=Response, include_in_schema=False)
async def test_push(
    user_id: int,
    message_type: str,
    title: str,
    content: dict,
    level: str = "info",
    db: Session = Depends(get_db)
):
    """测试推送接口（仅开发环境使用）"""
    success = await push_service.push_message(
        db=db,
        user_id=user_id,
        message_type=message_type,
        title=title,
        content=content,
        level=level
    )
    return Response.success(data={"push_success": success})
