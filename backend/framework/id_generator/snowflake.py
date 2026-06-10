"""
雪花算法ID生成器
基于Twitter的Snowflake算法实现，支持分布式环境下的唯一ID生成
ID结构：
+--------------------------------------------------------------------------+
| 1位 符号位 | 41位 时间戳(毫秒) | 5位 数据中心ID | 5位 工作节点ID | 12位 序列号 |
+--------------------------------------------------------------------------+
"""
import time
import asyncio
from typing import Optional, Tuple

from backend.framework.id_generator.redis_worker_id_allocator import RedisWorkerIdAllocator


class SnowflakeIdGenerator:
    """
    雪花算法ID生成器
    """

    # 开始时间戳 (2024-01-01 00:00:00)
    START_TIMESTAMP = 1704067200000

    # 每部分的位数
    WORKER_ID_BITS = 5
    DATA_CENTER_ID_BITS = 5
    SEQUENCE_BITS = 12

    # 每部分的最大值
    MAX_WORKER_ID = (1 << WORKER_ID_BITS) - 1  # 31
    MAX_DATA_CENTER_ID = (1 << DATA_CENTER_ID_BITS) - 1  # 31
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1  # 4095

    # 每部分的位移
    WORKER_ID_SHIFT = SEQUENCE_BITS
    DATA_CENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATA_CENTER_ID_BITS

    def __init__(
        self,
        worker_id: int,
        data_center_id: int = 0,
        worker_id_allocator: Optional[RedisWorkerIdAllocator] = None
    ):
        """
        初始化雪花算法生成器
        :param worker_id: 工作节点ID (0~31)
        :param data_center_id: 数据中心ID (0~31)，默认0
        :param worker_id_allocator: 可选的worker_id分配器，用于自动续期和重新分配
        """
        if worker_id < 0 or worker_id > self.MAX_WORKER_ID:
            raise ValueError(f"Worker ID must be between 0 and {self.MAX_WORKER_ID}")
        if data_center_id < 0 or data_center_id > self.MAX_DATA_CENTER_ID:
            raise ValueError(f"Data Center ID must be between 0 and {self.MAX_DATA_CENTER_ID}")

        self.worker_id = worker_id
        self.data_center_id = data_center_id
        self.worker_id_allocator = worker_id_allocator

        # 序列号
        self.sequence = 0
        # 上次生成ID的时间戳
        self.last_timestamp = -1
        # 锁，用于多线程/协程环境下的并发控制
        self._lock = asyncio.Lock()

    @classmethod
    async def create_with_redis_allocator(
        cls,
        service_name: str = "default_service",
        data_center_id: int = 0
    ) -> 'SnowflakeIdGenerator':
        """
        使用Redis分配器创建雪花算法生成器
        :param service_name: 服务名称
        :param data_center_id: 数据中心ID
        :return: SnowflakeIdGenerator实例
        """
        allocator = RedisWorkerIdAllocator(service_name)
        worker_id = await allocator.initialize()
        return cls(worker_id, data_center_id, allocator)

    def _get_current_timestamp(self) -> int:
        """
        获取当前时间戳（毫秒）
        :return: 当前时间戳
        """
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp: int) -> int:
        """
        等待下一毫秒
        :param last_timestamp: 上次生成ID的时间戳
        :return: 新的时间戳
        """
        timestamp = self._get_current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_current_timestamp()
        return timestamp

    async def generate_id(self) -> int:
        """
        生成下一个ID
        :return: 唯一ID
        """
        async with self._lock:
            timestamp = self._get_current_timestamp()

            # 如果当前时间小于上次生成ID的时间戳，说明系统时钟回退过
            if timestamp < self.last_timestamp:
                # 时钟回退处理：如果回退时间小于500ms，等待时钟追上
                if self.last_timestamp - timestamp < 500:
                    await asyncio.sleep((self.last_timestamp - timestamp) / 1000)
                    timestamp = self._get_current_timestamp()
                    if timestamp < self.last_timestamp:
                        # 等待后仍然回退，抛出异常
                        raise RuntimeError(
                            f"Clock moved backwards. Refusing to generate id for {self.last_timestamp - timestamp} milliseconds"
                        )
                else:
                    # 回退时间太长，抛出异常
                    raise RuntimeError(
                        f"Clock moved backwards. Refusing to generate id for {self.last_timestamp - timestamp} milliseconds"
                    )

            # 同一毫秒内，序列号递增
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                # 序列号溢出，等待下一毫秒
                if self.sequence == 0:
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                # 不同毫秒，序列号重置为0
                self.sequence = 0

            self.last_timestamp = timestamp

            # 组合ID
            id = (
                ((timestamp - self.START_TIMESTAMP) << self.TIMESTAMP_SHIFT) |
                (self.data_center_id << self.DATA_CENTER_ID_SHIFT) |
                (self.worker_id << self.WORKER_ID_SHIFT) |
                self.sequence
            )

            return id

    async def generate_string_id(self) -> str:
        """
        生成字符串类型的ID
        :return: 唯一ID字符串
        """
        return str(await self.generate_id())

    def parse_id(self, id: int) -> Tuple[int, int, int, int]:
        """
        解析ID，获取各个部分的值
        :param id: 要解析的ID
        :return: (timestamp, data_center_id, worker_id, sequence)
        """
        timestamp = (id >> self.TIMESTAMP_SHIFT) + self.START_TIMESTAMP
        data_center_id = (id >> self.DATA_CENTER_ID_SHIFT) & self.MAX_DATA_CENTER_ID
        worker_id = (id >> self.WORKER_ID_SHIFT) & self.MAX_WORKER_ID
        sequence = id & self.MAX_SEQUENCE
        return timestamp, data_center_id, worker_id, sequence

    async def close(self) -> None:
        """
        关闭生成器，释放资源
        """
        if self.worker_id_allocator:
            await self.worker_id_allocator.release()


# 全局实例
_global_generator: Optional[SnowflakeIdGenerator] = None


async def initialize_global_generator(service_name: str = "default_service", data_center_id: int = 0) -> None:
    """
    初始化全局ID生成器
    :param service_name: 服务名称
    :param data_center_id: 数据中心ID
    """
    global _global_generator
    if _global_generator is None:
        _global_generator = await SnowflakeIdGenerator.create_with_redis_allocator(service_name, data_center_id)


async def get_next_id() -> int:
    """
    获取下一个全局唯一ID
    :return: 唯一ID
    """
    if _global_generator is None:
        raise RuntimeError("Global ID generator not initialized. Call initialize_global_generator() first.")
    return await _global_generator.generate_id()


async def get_next_string_id() -> str:
    """
    获取下一个全局唯一ID字符串
    :return: 唯一ID字符串
    """
    if _global_generator is None:
        raise RuntimeError("Global ID generator not initialized. Call initialize_global_generator() first.")
    return await _global_generator.generate_string_id()


async def close_global_generator() -> None:
    """
    关闭全局ID生成器
    """
    global _global_generator
    if _global_generator:
        await _global_generator.close()
        _global_generator = None
