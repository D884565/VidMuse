# backend/v1/app/search/core/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import SearchQuery, SearchResult

class SearchChannel(ABC):
    """检索渠道接口"""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """渠道名称，唯一标识"""
        pass

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """渠道类型：vector_db, mysql, http_api等"""
        pass

    @abstractmethod
    def search(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        执行检索
        :param query: 检索查询对象
        :param context: 上下文信息
        :return: 检索结果列表
        """
        pass

    @abstractmethod
    async def asearch(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        异步执行检索
        :param query: 检索查询对象
        :param context: 上下文信息
        :return: 检索结果列表
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass

class BaseProcessor(ABC):
    """处理器基类"""

    @property
    @abstractmethod
    def processor_name(self) -> str:
        """处理器名称"""
        pass

    @abstractmethod
    def process(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        处理数据
        :param data: 输入数据（查询或结果）
        :param context: 上下文信息
        :return: 处理后的数据
        """
        pass

    @abstractmethod
    async def aprocess(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        异步处理数据
        :param data: 输入数据（查询或结果）
        :param context: 上下文信息
        :return: 处理后的数据
        """
        pass

class QueryEnhancementProcessor(BaseProcessor, ABC):
    """查询增强处理器基类"""
    @abstractmethod
    def process(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> SearchQuery:
        pass

    @abstractmethod
    async def aprocess(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> SearchQuery:
        pass

class PostProcessingProcessor(BaseProcessor, ABC):
    """结果后处理器基类"""
    @abstractmethod
    def process(self, results: List[SearchResult], context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        pass

    @abstractmethod
    async def aprocess(self, results: List[SearchResult], context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        pass
