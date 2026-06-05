# backend/v1/app/push/controller/websocket_controller.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import logging
import json

from backend.store.database.async_database import get_db
from ..middleware.ws_auth import get_ws_user
from ..service.connection_manager import connection_manager
from ..service.push_service import push_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int = Depends(get_ws_user),
    db: Session = Depends(get_db)
):
    """
    WebSocket连接端点
    通过query参数携带token进行鉴权：/v1/ws/connect?token=xxx
    """
    if user_id is None:
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

        # 监听客户端消息（目前只需要接收心跳）
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # 处理心跳
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": message.get("timestamp")})
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON from user {user_id}: {data}")

    except WebSocketDisconnect:
        connection_manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        connection_manager.disconnect(user_id, websocket)
