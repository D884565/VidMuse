from typing import List, Optional
from .base import BaseRetrieverImpl
from ..core import Query, Document
from .vector_retriever import VectorRetriever
from .keyword_retriever import KeywordRetriever

class HybridRetriever(BaseRetrieverImpl):
    """
    混合检索器
    结合语义检索和关键词检索的结果
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        vector_retriever: Optional[VectorRetriever] = None,
        keyword_retriever: Optional[KeywordRetriever] = None
    ):
        super().__init__(config)
        self.vector_retriever = vector_retriever or VectorRetriever(config)
        self.keyword_retriever = keyword_retriever or KeywordRetriever(config)
        # 语义检索结果的权重
        self.vector_weight = self.config.get("hybrid_vector_weight", 0.6)
        # 关键词检索结果的权重
        self.keyword_weight = self.config.get("hybrid_keyword_weight", 0.4)

    def _retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        # 并行执行两种检索（实际场景可以用asyncio实现）
        vector_docs = self.vector_retriever.retrieve(query, top_k)
        keyword_docs = self.keyword_retriever.retrieve(query, top_k)

        # 应用权重调整得分
        for doc in vector_docs:
            doc.score *= self.vector_weight
            doc.metadata["original_score"] = doc.score / self.vector_weight
            doc.metadata["weight"] = self.vector_weight

        for doc in keyword_docs:
            doc.score *= self.keyword_weight
            doc.metadata["original_score"] = doc.score / self.keyword_weight
            doc.metadata["weight"] = self.keyword_weight

        # 合并结果
        all_docs = vector_docs + keyword_docs

        # 按得分降序排序
        all_docs.sort(key=lambda x: x.score, reverse=True)

        return all_docs
