from abc import ABC, abstractmethod
from typing import List, Optional
from .models import Query, Document, SearchContext
from .exceptions import SearchBaseException

class BaseQueryEnhancer(ABC):
    """问题增强处理器抽象基类"""

    @abstractmethod
    def enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        """
        增强用户查询

        :param query: 原始查询对象
        :param context: 检索上下文
        :return: 增强后的查询对象
        :raises QueryEnhancementError: 问题增强处理失败时抛出
        """
        pass

class BaseRetriever(ABC):
    """检索器抽象基类"""

    @abstractmethod
    def retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        """
        执行检索

        :param query: 查询对象
        :param top_k: 返回结果数量
        :return: 检索到的文档列表
        :raises RetrievalError: 检索执行失败时抛出
        """
        pass

class BasePostProcessor(ABC):
    """后处理器抽象基类"""

    @abstractmethod
    def process(self, documents: List[Document], query: Query) -> List[Document]:
        """
        处理检索结果

        :param documents: 原始检索结果列表
        :param query: 查询对象
        :return: 处理后的文档列表
        :raises PostProcessingError: 后处理失败时抛出
        """
        pass

class BaseDataSourceChannel(ABC):
    """数据源通道抽象基类"""

    @abstractmethod
    def connect(self) -> None:
        """
        连接到数据源

        :raises DataSourceError: 连接失败时抛出
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开与数据源的连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查是否已连接到数据源"""
        pass
