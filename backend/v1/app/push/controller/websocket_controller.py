# backend/v1/app/push/controller/websocket_controller.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from starlette.websockets import WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json

from backend.store.database.async_database import get_db
from ..middleware.ws_auth import get_ws_user
from ..service.connection_manager import connection_manager
from ..service.push_service import push_service
from ..dao.message_dao import message_dao
from ..dto.message_schema import MessageQueryRequest

logger = logging.getLogger(__name__)

router = APIRouter()


async def _push_offline_messages(db: AsyncSession, user_id: int) -> None:
    """推送用户的离线未读消息"""
    try:
        # 查询最近100条未读消息
        query_params = MessageQueryRequest(
            page=1,
            page_size=100,
            is_read=False
        )
        total, unread_count, messages = await message_dao.get_user_messages(db, user_id, query_params)

        if unread_count == 0:
            logger.debug(f"User {user_id} has no offline messages")
            return

        logger.info(f"Pushing {unread_count} offline messages to user {user_id}")

        # 逐个推送未读消息
        for message in messages:
            # 转换为字典格式
            message_dict = {
                "message_id": message.message_id,
                "message_type": message.message_type,
                "title": message.title,
                "content": message.content,
                "level": message.level,
                "trace_id": message.trace_id,
                "business_type": message.business_type,
                "task_id": message.task_id,
                "task_domain": message.task_domain,
                "task_type": message.task_type,
                "project_id": message.project_id,
                "asset_id": message.asset_id,
                "event_type": message.event_type,
                "status": message.status,
                "progress": message.progress,
                "extra": message.extra,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "is_read": message.is_read,
                "offline": True  # 标记为离线消息
            }

            # 推送消息
            await connection_manager.publish_personal_message(message_dict, user_id)

    except Exception as e:
        logger.error(f"Failed to push offline messages for user {user_id}: {e}", exc_info=True)


@router.websocket("/ws/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int = Depends(get_ws_user),
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket连接端点
    通过query参数携带token进行鉴权：/v1/ws/connect?token=xxx
    """
    if user_id is None:
        # 鉴权失败时已经在get_ws_user中关闭了连接，直接返回
        return

    await connection_manager.connect(user_id, websocket)

    try:
        # 发送欢迎消息
        await push_service.push_message(
            db=db,
            user_id=user_id,
            message_type="system",
            title="连接成功",
            content="WebSocket连接已建立，您将收到实时消息推送",
            level="success",
            persist=False  # 不持久化连接消息
        )

        # 推送离线未读消息
        await _push_offline_messages(db, user_id)

        # 监听客户端消息（目前只需要接收心跳）
        while True:
            # 检查连接状态，避免在已断开的连接上调用receive_text
            if websocket.application_state != WebSocketState.CONNECTED:
                logger.info(f"WebSocket connection already closed for user {user_id}")
                raise WebSocketDisconnect()

            try:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    # 处理心跳
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": message.get("timestamp")})
                    # 处理消息确认
                    elif message.get("type") == "ack":
                        message_ids = message.get("message_ids", [])
                        if message_ids:
                            await message_dao.mark_messages_as_read(db, user_id, message_ids)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from user {user_id}: {data}")
            except RuntimeError as e:
                if "WebSocket is not connected" in str(e):
                    # 连接已经断开，视为正常断开
                    logger.info(f"WebSocket connection closed unexpectedly for user {user_id}")
                    raise WebSocketDisconnect()
                raise

    except WebSocketDisconnect:
        connection_manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        connection_manager.disconnect(user_id, websocket)
