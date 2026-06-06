# backend/v1/app/push/middleware/ws_auth.py
from fastapi import WebSocket, status, Query
from typing import Optional
from sqlalchemy.orm import Session

from backend.v1.app.config.config import settings
from backend.v1.app.user.service.user_service import user_service
from backend.framework.exceptions.exceptions import BusinessException
from backend.store.database.sync_database import get_db


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

        # 获取数据库会话
        db: Session = next(get_db())

        try:
            # 检查用户是否存在
            user_service.get_user_info(db, user_id)
            return user_id
        finally:
            db.close()

    except BusinessException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="令牌无效或用户不存在")
        return None
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败")
        return None
