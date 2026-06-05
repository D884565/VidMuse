# backend/v1/app/push/service/push_service.py
from typing import Any, Optional
import uuid
import json
from sqlalchemy.orm import Session
import logging

from backend.framework.trace import get_trace_id, trace
from .connection_manager import connection_manager
from ..dao.message_dao import message_dao
from ..dto.message_schema import PushMessageCreate, PushMessageBase

logger = logging.getLogger(__name__)


class PushService:
    """推送服务"""

    @staticmethod
    @trace
    async def push_message(
        db: Session,
        user_id: int,
        message_type: str,
        title: str,
        content: Any,
        level: str = "info",
        trace_id: Optional[str] = None,
        extra: Optional[dict] = None,
        persist: bool = True
    ) -> bool:
        """
        向用户推送消息
        :param db: 数据库会话
        :param user_id: 目标用户ID
        :param message_type: 消息类型
        :param title: 消息标题
        :param content: 消息内容
        :param level: 消息级别
        :param trace_id: 关联的trace_id，默认从当前上下文获取
        :param extra: 扩展字段
        :param persist: 是否持久化到数据库
        :return: 是否推送成功（至少有一个在线连接收到）
        """
        # 自动获取trace_id
        if trace_id is None:
            trace_id = get_trace_id()

        # 生成消息ID
        message_id = uuid.uuid4().hex

        # 创建消息对象
        message_create = PushMessageCreate(
            user_id=user_id,
            message_type=message_type,
            title=title,
            content=content,
            level=level,
            trace_id=trace_id,
            extra=extra
        )

        # 持久化消息
        if persist:
            db_message = message_dao.create_message(db, message_create, message_id)
            message_dict = PushMessageBase.from_orm(db_message).model_dump()
        else:
            message_dict = {
                "message_id": message_id,
                "message_type": message_type,
                "title": title,
                "content": content,
                "level": level,
                "trace_id": trace_id,
                "extra": extra,
                "created_at": None  # 非持久化消息没有创建时间
            }

        # 转换为JSON可序列化格式
        if message_dict.get("created_at"):
            message_dict["created_at"] = message_dict["created_at"].isoformat()

        # 推送消息
        success = await connection_manager.send_personal_message(message_dict, user_id)

        logger.info(
            f"Pushed message {message_id} to user {user_id}, "
            f"type: {message_type}, success: {success}, persisted: {persist}"
        )

        return success

    @staticmethod
    async def broadcast_message(
        message_type: str,
        title: str,
        content: Any,
        level: str = "info",
        extra: Optional[dict] = None
    ) -> None:
        """
        广播消息给所有在线用户（不持久化）
        :param message_type: 消息类型
        :param title: 消息标题
        :param content: 消息内容
        :param level: 消息级别
        :param extra: 扩展字段
        """
        message_id = uuid.uuid4().hex
        message_dict = {
            "message_id": message_id,
            "message_type": message_type,
            "title": title,
            "content": content,
            "level": level,
            "trace_id": None,
            "extra": extra,
            "created_at": None
        }

        await connection_manager.broadcast(message_dict)
        logger.info(f"Broadcast message {message_id}, type: {message_type}")


# 全局服务实例
push_service = PushService()