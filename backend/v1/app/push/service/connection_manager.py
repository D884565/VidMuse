from typing import Dict, List
from fastapi import WebSocket
import logging
import asyncio
from threading import Lock

from .redis_client import redis_client

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 用户ID到WebSocket连接列表的映射
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # 线程锁，保护active_connections的并发访问
        self._lock = Lock()
        # Redis频道名称
        self._push_channel = "ws:push:message"
        self._broadcast_channel = "ws:broadcast:message"

    # ====================== 异步初始化 ======================
    async def initialize(self):
        """初始化 Redis 订阅（必须异步）"""
        # 先初始化 redis 客户端
        await redis_client.initialize()
        # 订阅个人消息频道
        await redis_client.subscribe(self._push_channel, self._handle_redis_push_message)
        # 订阅广播消息频道
        await redis_client.subscribe(self._broadcast_channel, self._handle_redis_broadcast_message)
        logger.info("Redis channels subscribed successfully")

    def _handle_redis_push_message(self, data: dict) -> None:
        """处理来自Redis的个人推送消息"""
        user_id = data.get("user_id")
        message = data.get("message")

        if not user_id or not message:
            logger.warning(f"Invalid push message from Redis: {data}")
            return

        # 在后台任务中发送消息
        asyncio.create_task(self.send_personal_message(message, user_id))

    def _handle_redis_broadcast_message(self, data: dict) -> None:
        """处理来自Redis的广播消息"""
        message = data.get("message")

        if not message:
            logger.warning(f"Invalid broadcast message from Redis: {data}")
            return

        # 在后台任务中发送消息
        asyncio.create_task(self.broadcast(message))

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """建立连接"""
        await websocket.accept()
        with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected, total connections: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """断开连接"""
        with self._lock:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                    # 如果用户没有连接了，删除key
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
                    logger.info(f"User {user_id} disconnected, remaining connections: {len(self.active_connections.get(user_id, []))}")

    async def send_personal_message(self, message: dict, user_id: int) -> bool:
        """向指定用户发送消息"""
        with self._lock:
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
                with self._lock:
                    if connection in self.active_connections.get(user_id, []):
                        self.active_connections[user_id].remove(connection)

        # 清理空的连接列表
        with self._lock:
            if user_id in self.active_connections and not self.active_connections[user_id]:
                del self.active_connections[user_id]

        return success

    async def broadcast(self, message: dict) -> None:
        """向所有在线用户广播消息"""
        with self._lock:
            user_ids = list(self.active_connections.keys())

        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def publish_personal_message(self, message: dict, user_id: int) -> None:
        """通过Redis发布个人消息，支持多worker环境"""
        await redis_client.publish(
            self._push_channel,
            {
                "user_id": user_id,
                "message": message
            }
        )

    async def publish_broadcast(self, message: dict) -> None:
        """通过Redis发布广播消息，支持多worker环境"""
        await redis_client.publish(
            self._broadcast_channel,
            {
                "message": message
            }
        )

    def get_online_user_count(self) -> int:
        """获取在线用户数量"""
        with self._lock:
            return len(self.active_connections)

    def get_user_connection_count(self, user_id: int) -> int:
        """获取用户的连接数量"""
        with self._lock:
            return len(self.active_connections.get(user_id, []))


# 全局连接管理器实例
connection_manager = ConnectionManager()
