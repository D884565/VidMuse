"""记忆系统抽象基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

class BaseMemory(ABC):
    """记忆抽象基类，定义所有记忆系统的通用接口"""

    @abstractmethod
    def add(self, content: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        添加记忆内容
        :param content: 记忆内容，可以是任意类型
        :param metadata: 元数据，如时间戳、类型、来源等
        :return: 记忆ID
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        :param query: 查询关键词
        :param top_k: 返回最相关的前k条
        :return: 相关记忆列表，每条包含content和metadata
        """
        pass

    @abstractmethod
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的记忆
        :param limit: 返回数量限制
        :return: 最近的记忆列表
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有记忆"""
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """
        删除指定记忆
        :param memory_id: 记忆ID
        :return: 是否删除成功
        """
        pass

class BaseShortTermMemory(BaseMemory):
    """短期记忆抽象基类，存储会话相关的临时记忆"""
    pass

class BaseLongTermMemory(BaseMemory):
    """长期记忆抽象基类，存储持久化的知识和经验"""
    pass
