"""
ID生成器模块
提供基于雪花算法的分布式唯一ID生成功能
"""

from backend.framework.id_generator.snowflake import (
    SnowflakeIdGenerator,
    initialize_global_generator,
    get_next_id,
    get_next_string_id,
    close_global_generator
)
from backend.framework.id_generator.redis_worker_id_allocator import RedisWorkerIdAllocator

__all__ = [
    'SnowflakeIdGenerator',
    'RedisWorkerIdAllocator',
    'initialize_global_generator',
    'get_next_id',
    'get_next_string_id',
    'close_global_generator'
]
