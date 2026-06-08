# backend/v1/app/push/dao/message_dao.py
from typing import Optional, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..model.message_model import PushMessage, UserMessage
from ..dto.message_schema import PushMessageCreate, MessageQueryRequest


@dataclass
class UserMessageWithStatus:
    """用户消息带阅读状态的数据类"""
    message_id: str
    message_type: str
    title: str
    content: Any
    level: str
    trace_id: Optional[str]
    business_type: Optional[str]
    task_id: Optional[str]
    task_domain: Optional[str]
    task_type: Optional[str]
    project_id: Optional[int]
    asset_id: Optional[int]
    event_type: Optional[str]
    status: Optional[str]
    progress: Optional[int]
    extra: Optional[dict]
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime]


class MessageDAO:
    """消息数据访问层"""

    @staticmethod
    def create_message(
        db: Session,
        message_create: PushMessageCreate,
        message_id: str,
        *,
        commit: bool = True,
    ) -> PushMessage:
        """创建消息"""
        db_message = PushMessage(
            message_id=message_id,
            message_type=message_create.message_type,
            title=message_create.title,
            content=message_create.content,
            level=message_create.level,
            trace_id=message_create.trace_id,
            business_type=message_create.business_type,
            task_id=message_create.task_id,
            task_domain=message_create.task_domain,
            task_type=message_create.task_type,
            project_id=message_create.project_id,
            asset_id=message_create.asset_id,
            event_type=message_create.event_type,
            status=message_create.status,
            progress=message_create.progress,
            extra=message_create.extra
        )
        db.add(db_message)

        # 创建用户关联
        db_user_message = UserMessage(
            user_id=message_create.user_id,
            message_id=message_id
        )
        db.add(db_user_message)

        if commit:
            db.commit()
        else:
            db.flush()
        db.refresh(db_message)
        return db_message

    @staticmethod
    def get_user_messages(
        db: Session,
        user_id: int,
        query_params: MessageQueryRequest
    ) -> Tuple[int, int, List[UserMessageWithStatus]]:
        """查询用户消息列表"""
        query = db.query(
            PushMessage,
            UserMessage.is_read,
            UserMessage.read_at
        ).join(
            UserMessage,
            PushMessage.message_id == UserMessage.message_id
        ).filter(
            UserMessage.user_id == user_id
        )

        # 筛选条件
        if query_params.message_type:
            query = query.filter(PushMessage.message_type == query_params.message_type)
        if query_params.start_time:
            query = query.filter(PushMessage.created_at >= query_params.start_time)
        if query_params.end_time:
            query = query.filter(PushMessage.created_at <= query_params.end_time)
        if query_params.is_read is not None:
            query = query.filter(UserMessage.is_read == query_params.is_read)

        # 总数量
        total = query.count()

        # 未读数量
        unread_count = db.query(func.count(UserMessage.id)).filter(
            UserMessage.user_id == user_id,
            UserMessage.is_read == False
        ).scalar()

        # 分页
        offset = (query_params.page - 1) * query_params.page_size
        result = query.order_by(desc(PushMessage.created_at))\
            .offset(offset)\
            .limit(query_params.page_size)\
            .all()

        # 转换为带状态的消息对象
        messages = [
            UserMessageWithStatus(
                message_id=msg.message_id,
                message_type=msg.message_type,
                title=msg.title,
                content=msg.content,
                level=msg.level,
                trace_id=msg.trace_id,
                business_type=msg.business_type,
                task_id=msg.task_id,
                task_domain=msg.task_domain,
                task_type=msg.task_type,
                project_id=msg.project_id,
                asset_id=msg.asset_id,
                event_type=msg.event_type,
                status=msg.status,
                progress=msg.progress,
                extra=msg.extra,
                created_at=msg.created_at,
                is_read=is_read,
                read_at=read_at
            )
            for msg, is_read, read_at in result
        ]

        return total, unread_count, messages

    @staticmethod
    def mark_messages_as_read(db: Session, user_id: int, message_ids: List[str]) -> int:
        """标记消息为已读"""
        updated = db.query(UserMessage).filter(
            UserMessage.user_id == user_id,
            UserMessage.message_id.in_(message_ids),
            UserMessage.is_read == False
        ).update(
            {"is_read": True, "read_at": datetime.now()},
            synchronize_session=False
        )
        db.commit()
        return updated

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """获取用户未读消息数量"""
        return db.query(func.count(UserMessage.id)).filter(
            UserMessage.user_id == user_id,
            UserMessage.is_read == False
        ).scalar()


# 全局DAO实例
message_dao = MessageDAO()
