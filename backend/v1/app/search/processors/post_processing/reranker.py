from typing import List, Optional
from .base import BasePostProcessorImpl
from backend.v1.app.search.core import Query, Document

class Reranker(BasePostProcessorImpl):
    """
    结果重排序器
    基于语义相似度或业务规则对检索结果重新排序
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.rerank_top_k = self.config.get("rerank_top_k", 20)
        self.reranking_method = self.config.get("reranking_method", "semantic")  # semantic or rule_based

    def _process(self, documents: List[Document], query: Query) -> List[Document]:
        if not documents:
            return []

        # 只对前N个结果进行重排序，提高效率
        rerank_candidates = documents[:self.rerank_top_k]
        remaining = documents[self.rerank_top_k:]

        if self.reranking_method == "semantic":
            reranked = self._semantic_rerank(rerank_candidates, query)
        elif self.reranking_method == "rule_based":
            reranked = self._rule_based_rerank(rerank_candidates, query)
        else:
            reranked = rerank_candidates

        return reranked + remaining

    def _semantic_rerank(self, documents: List[Document], query: Query) -> List[Document]:
        """基于语义相似度重排序，实际场景需要调用交叉编码器模型"""
        # 这里是模拟实现，实际需要用交叉编码器计算query和document的相似度
        # 模拟：对得分进行微小调整，模拟重排序效果
        for i, doc in enumerate(documents):
            # 模拟重排序得分，在原始得分基础上有±0.05的波动
            import random
            adjustment = random.uniform(-0.05, 0.05)
            doc.metadata["original_rank"] = i
            doc.metadata["rerank_adjustment"] = adjustment
            doc.score = max(0.0, min(1.0, doc.score + adjustment))

        # 重新排序
        documents.sort(key=lambda x: x.score, reverse=True)

        for i, doc in enumerate(documents):
            doc.metadata["new_rank"] = i

        return documents

    def _rule_based_rerank(self, documents: List[Document], query: Query) -> List[Document]:
        """基于业务规则的重排序"""
        # 规则1：高优先级的数据源排在前面
        source_priority = {"sql": 3, "vector": 2, "keyword": 1, "api": 0}

        # 规则2：标题中包含关键词的排在前面
        query_text = query.text.lower()

        def get_rank_score(doc: Document) -> float:
            priority_score = source_priority.get(doc.source, 0) * 0.2
            title_match = 0.3 if doc.title and query_text in doc.title.lower() else 0.0
            content_match = 0.1 if query_text in doc.content.lower() else 0.0
            total = doc.score + priority_score + title_match + content_match
            return total

        documents.sort(key=get_rank_score, reverse=True)

        return documents
