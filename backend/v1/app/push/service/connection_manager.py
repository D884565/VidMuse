from typing import Dict, List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 用户ID到WebSocket连接列表的映射
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """建立连接"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected, total connections: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """断开连接"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                # 如果用户没有连接了，删除key
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                logger.info(f"User {user_id} disconnected, remaining connections: {len(self.active_connections.get(user_id, []))}")

    async def send_personal_message(self, message: dict, user_id: int) -> bool:
        """向指定用户发送消息"""
        if user_id not in self.active_connections:
            logger.debug(f"User {user_id} has no active connections")
            return False

        success = False
        # 复制一份列表，避免遍历过程中修改
        connections = self.active_connections[user_id].copy()
        for connection in connections:
            try:
                await connection.send_json(message)
                success = True
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                # 移除失效连接
                if connection in self.active_connections.get(user_id, []):
                    self.active_connections[user_id].remove(connection)

        # 清理空的连接列表
        if user_id in self.active_connections and not self.active_connections[user_id]:
            del self.active_connections[user_id]

        return success

    async def broadcast(self, message: dict) -> None:
        """向所有在线用户广播消息"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)

    def get_online_user_count(self) -> int:
        """获取在线用户数量"""
        return len(self.active_connections)

    def get_user_connection_count(self, user_id: int) -> int:
        """获取用户的连接数量"""
        return len(self.active_connections.get(user_id, []))


# 全局连接管理器实例
connection_manager = ConnectionManager()
