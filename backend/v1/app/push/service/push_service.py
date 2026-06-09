# backend/v1/app/push/service/push_service.py
from typing import Any, Optional
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.framework.trace import get_trace_id, trace
from .connection_manager import connection_manager
from ..dao.message_dao import message_dao
from ..dto.message_schema import PushMessageCreate, PushMessageBase
from backend.v1.app.user.dao.user_dao import UserDAO

logger = logging.getLogger(__name__)


class PushService:
    """推送服务"""

    @staticmethod
    async def push_message(
        db: AsyncSession,
        user_id: int,
        message_type: str,
        title: str,
        content: Any,
        level: str = "info",
        trace_id: Optional[str] = None,
        extra: Optional[dict] = None,
        business_type: Optional[str] = None,
        task_id: Optional[str] = None,
        task_domain: Optional[str] = None,
        task_type: Optional[str] = None,
        project_id: Optional[int] = None,
        asset_id: Optional[int] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        progress: Optional[int] = None,
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
            business_type=business_type,
            task_id=task_id,
            task_domain=task_domain,
            task_type=task_type,
            project_id=project_id,
            asset_id=asset_id,
            event_type=event_type,
            status=status,
            progress=progress,
            extra=extra
        )

        # 持久化消息
        if persist:
            db_message = await message_dao.create_message(db, message_create, message_id)
            message_dict = PushMessageBase.from_orm(db_message).model_dump()
        else:
            message_dict = {
                "message_id": message_id,
                "message_type": message_type,
                "title": title,
                "content": content,
                "level": level,
                "trace_id": trace_id,
                "business_type": business_type,
                "task_id": task_id,
                "task_domain": task_domain,
                "task_type": task_type,
                "project_id": project_id,
                "asset_id": asset_id,
                "event_type": event_type,
                "status": status,
                "progress": progress,
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

    @staticmethod
    async def push_to_admin(
        db: AsyncSession,
        message_type: str,
        title: str,
        content: Any,
        level: str = "info",
        trace_id: Optional[str] = None,
        extra: Optional[dict] = None,
        persist: bool = True
    ) -> list[bool]:
        """
        向所有管理员推送消息
        :param db: 数据库会话
        :param message_type: 消息类型
        :param title: 消息标题
        :param content: 消息内容
        :param level: 消息级别
        :param trace_id: 关联的trace_id，默认从当前上下文获取
        :param extra: 扩展字段
        :param persist: 是否持久化到数据库
        :return: 推送结果列表
        """
        # 获取所有管理员用户（role=0，假设管理员角色值为0）
        # UserDAO目前还是同步实现，使用run_sync兼容
        total, admins = await db.run_sync(
            lambda sync_db: UserDAO.list_users(sync_db, role=0, page_size=1000)  # 假设管理员数量不超过1000
        )

        results = []
        for admin in admins:
            try:
                success = await PushService.push_message(
                    db=db,
                    user_id=admin.id,
                    message_type=message_type,
                    title=title,
                    content=content,
                    level=level,
                    trace_id=trace_id,
                    extra=extra,
                    persist=persist
                )
                results.append(success)
            except Exception as e:
                logger.error(f"向管理员 {admin.id} 推送消息失败: {str(e)}", exc_info=True)
                results.append(False)

        return results


# 全局服务实例
push_service = PushService()
