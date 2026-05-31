from typing import Optional
from backend.v1.app.search.core import BaseQueryEnhancer, Query, SearchContext, QueryEnhancementError

class BaseQueryEnhancerImpl(BaseQueryEnhancer):
    """问题增强处理器基类实现"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        """
        增强查询，子类需要实现_enhance方法
        """
        try:
            return self._enhance(query, context)
        except Exception as e:
            raise QueryEnhancementError(f"{self.__class__.__name__} failed: {str(e)}") from e

    def _enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        """
        实际的增强逻辑，子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement _enhance method")
