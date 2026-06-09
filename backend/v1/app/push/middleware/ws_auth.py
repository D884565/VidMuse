# backend/v1/app/push/middleware/ws_auth.py
from fastapi import WebSocket, status, Query
from typing import Optional
import logging
import asyncio

from backend.v1.app.config.config import settings
from backend.v1.app.user.service.user_service import user_service
from backend.framework.exceptions.exceptions import BusinessException
from backend.store.database.sync_database import get_db

logger = logging.getLogger(__name__)


async def get_ws_user(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT认证令牌")
) -> Optional[int]:
    """
    WebSocket连接鉴权，返回用户ID
    鉴权失败返回None，调用方需要关闭连接
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="缺少认证令牌")
        return None

    try:
        # 从token解析用户ID
        user_id: int = user_service.get_user_id_from_token(token)

        # 在独立线程中运行同步数据库操作，避免阻塞事件循环
        def _check_user_exists():
            db = None
            try:
                db = next(get_db())
                # 检查用户是否存在
                user_service.get_user_info(db, user_id)
                return True
            finally:
                if db:
                    try:
                        db.close()
                    except Exception as e:
                        logger.error(f"关闭数据库会话失败: {str(e)}")

        await asyncio.to_thread(_check_user_exists)
        return user_id

    except BusinessException as e:
        logger.warning(f"WebSocket鉴权失败: {str(e)}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="令牌无效或用户不存在")
        return None
    except Exception as e:
        logger.error(f"WebSocket认证错误: {str(e)}", exc_info=True)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败")
        return None
