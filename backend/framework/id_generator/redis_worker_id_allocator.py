"""
基于Redis的工作节点ID分配器
用于雪花算法的worker_id分配，确保分布式环境下每个节点的worker_id唯一
"""
import asyncio
import time
from typing import Optional
import redis.asyncio as redis

from backend.v1.app.config.config import settings


class RedisWorkerIdAllocator:
    """
    使用Redis实现的工作节点ID分配器
    原理：
    1. 每个服务实例启动时，向Redis注册自己的服务标识
    2. Redis使用递增计数器分配唯一的worker_id
    3. 服务实例定期续期自己的worker_id，避免进程异常退出导致的ID浪费
    4. 当服务实例正常退出时，释放worker_id
    """

    # Redis中存储worker_id分配的key
    WORKER_ID_COUNTER_KEY = "id_generator:worker_id_counter"
    # Redis中存储worker_id租期的key前缀
    WORKER_ID_LEASE_PREFIX = "id_generator:worker_lease:"
    # 最大worker_id值 (10位 = 0~1023)
    MAX_WORKER_ID = 1023
    # 租期时间，默认300秒
    LEASE_TTL = 300
    # 续期间隔，默认100秒
    LEASE_RENEW_INTERVAL = 100

    def __init__(self, service_name: str = "default_service"):
        """
        初始化分配器
        :param service_name: 服务名称，用于区分不同服务的worker_id
        """
        self.service_name = service_name
        self.redis_client: Optional[redis.Redis] = None
        self.worker_id: Optional[int] = None
        self._lease_renew_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self) -> int:
        """
        初始化分配器，获取worker_id
        :return: 分配到的worker_id
        """
        # 初始化redis客户端
        if not self.redis_client:
            self.redis_client = redis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
                decode_responses=True
            )

        # 尝试获取worker_id
        self.worker_id = await self._allocate_worker_id()

        # 启动后台续期任务
        self._running = True
        self._lease_renew_task = asyncio.create_task(self._lease_renew_loop())

        return self.worker_id

    async def _allocate_worker_id(self) -> int:
        """
        分配worker_id
        :return: 分配到的worker_id
        """
        # 首先尝试查找是否有已经分配过的worker_id（如果是重启的话）
        current_worker_id = await self._find_existing_worker_id()
        if current_worker_id is not None:
            # 续期
            await self._renew_lease(current_worker_id)
            return current_worker_id

        # 没有找到，尝试分配新的
        while True:
            # 递增计数器
            worker_id = await self.redis_client.incr(self.WORKER_ID_COUNTER_KEY) - 1

            # 如果超过最大值，重置计数器
            if worker_id > self.MAX_WORKER_ID:
                await self.redis_client.set(self.WORKER_ID_COUNTER_KEY, 1)
                worker_id = 0

            # 尝试获取这个worker_id的租约
            success = await self._try_acquire_lease(worker_id)
            if success:
                return worker_id

    async def _find_existing_worker_id(self) -> Optional[int]:
        """
        查找当前服务实例是否已经分配过worker_id
        :return: 如果有返回worker_id，否则返回None
        """
        # 使用服务名 + 主机名？暂时简化，每次都重新分配
        # 实际生产环境可以根据具体需求实现实例识别逻辑
        return None

    async def _try_acquire_lease(self, worker_id: int) -> bool:
        """
        尝试获取指定worker_id的租约
        :param worker_id: 要获取的worker_id
        :return: 是否获取成功
        """
        key = f"{self.WORKER_ID_LEASE_PREFIX}{worker_id}"
        # 使用SETNX尝试获取锁
        success = await self.redis_client.set(
            key,
            self.service_name,
            ex=self.LEASE_TTL,
            nx=True
        )
        return success is not None

    async def _renew_lease(self, worker_id: int) -> None:
        """
        续期worker_id的租约
        :param worker_id: 要续期的worker_id
        """
        key = f"{self.WORKER_ID_LEASE_PREFIX}{worker_id}"
        await self.redis_client.expire(key, self.LEASE_TTL)

    async def _lease_renew_loop(self) -> None:
        """
        后台续期循环
        """
        try:
            while self._running and self.worker_id is not None:
                await asyncio.sleep(self.LEASE_RENEW_INTERVAL)
                try:
                    await self._renew_lease(self.worker_id)
                except Exception as e:
                    # 续期失败，尝试重新分配
                    self.worker_id = await self._allocate_worker_id()
        except asyncio.CancelledError:
            pass

    async def release(self) -> None:
        """
        释放worker_id
        """
        self._running = False
        if self._lease_renew_task:
            self._lease_renew_task.cancel()
            try:
                await self._lease_renew_task
            except asyncio.CancelledError:
                pass

        if self.worker_id is not None and self.redis_client:
            key = f"{self.WORKER_ID_LEASE_PREFIX}{self.worker_id}"
            await self.redis_client.delete(key)

        if self.redis_client:
            await self.redis_client.close()

    def get_worker_id(self) -> Optional[int]:
        """
        获取当前的worker_id
        :return: worker_id
        """
        return self.worker_id
