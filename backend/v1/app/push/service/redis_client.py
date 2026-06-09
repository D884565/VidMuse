"""
Redis客户端封装
提供Redis连接和发布订阅功能
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Any
from redis.asyncio import Redis
from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端单例"""
    _instance: Optional['RedisClient'] = None
    _redis: Optional[Redis] = None
    _pubsub: Optional[Any] = None
    _listener_task: Optional[asyncio.Task] = None
    _message_handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}


    def __new__(cls) -> 'RedisClient':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """初始化Redis连接"""
        if self._redis is None:
            self._redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True
            )
            logger.info("Redis client initialized")
    
    def get_pubsub(self):
        if self._pubsub is None and self._redis is not None:
            self._pubsub = self._redis.pubsub()
        return self._pubsub

    async def close(self) -> None:
        """关闭Redis连接"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis client closed")

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """发布消息到指定频道"""
        if not self._redis:
            await self.initialize()

        await self._redis.publish(channel, json.dumps(message, ensure_ascii=False))
        logger.debug(f"Published message to channel {channel}: {message}")

    async def subscribe(self, channel: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """订阅频道并注册消息处理器"""
        if channel not in self._message_handlers:
            self._message_handlers[channel] = []

        self._message_handlers[channel].append(handler)
        logger.debug(f"Subscribed to channel {channel}")

        # 如果还没有启动监听器，启动它
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        """监听消息循环"""
        if not self._redis:
            await self.initialize()

        self._pubsub = self._redis.pubsub()

        # 订阅所有已注册的频道
        await self._pubsub.subscribe(*self._message_handlers.keys())

        logger.info("Redis pubsub listener started")

        try:
            while True:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        channel = message["channel"]
                        data = json.loads(message["data"])

                        # 调用该频道的所有处理器
                        if channel in self._message_handlers:
                            for handler in self._message_handlers[channel]:
                                try:
                                    handler(data)
                                except Exception as e:
                                    logger.error(f"Error handling message from channel {channel}: {e}", exc_info=True)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse Redis message: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("Redis pubsub listener cancelled")
        except Exception as e:
            logger.error(f"Redis pubsub listener error: {e}", exc_info=True)
        finally:
            if self._pubsub:
                await self._pubsub.close()
            logger.info("Redis pubsub listener stopped")


# 全局Redis客户端实例
redis_client = RedisClient()
