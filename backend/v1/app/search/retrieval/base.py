from typing import List, Optional
from ..core import BaseRetriever, Query, Document, RetrievalError
from ..config import RETRIEVAL_CONFIG

class BaseRetrieverImpl(BaseRetriever):
    """检索器基类实现"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or RETRIEVAL_CONFIG
        self.default_top_k = self.config.get("default_top_k", 10)
        self.min_score_threshold = self.config.get("min_score_threshold", 0.6)

    def retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        """
        执行检索，子类需要实现_retrieve方法
        """
        try:
            documents = self._retrieve(query, top_k)
            # 过滤低于阈值的结果
            filtered = [doc for doc in documents if doc.score >= self.min_score_threshold]
            return filtered[:top_k]
        except Exception as e:
            raise RetrievalError(f"{self.__class__.__name__} failed: {str(e)}") from e

    def _retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        """
        实际的检索逻辑，子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement _retrieve method")
