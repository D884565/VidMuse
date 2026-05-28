from typing import List, Optional, Dict
from .base import BasePostProcessorImpl
from ..core import Query, Document

class Merger(BasePostProcessorImpl):
    """
    结果合并器
    合并来自不同数据源或检索方式的结果
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        # 不同数据源的权重配置
        self.source_weights: Dict[str, float] = self.config.get("source_weights", {
            "vector": 1.0,
            "keyword": 0.9,
            "sql": 1.0,
            "api": 0.8
        })

    def _process(self, documents: List[Document], query: Query) -> List[Document]:
        if not documents:
            return []

        # 按数据源应用权重
        for doc in documents:
            weight = self.source_weights.get(doc.source, 1.0)
            doc.score *= weight
            doc.metadata["merge_weight"] = weight
            doc.metadata["original_score_before_merge"] = doc.score / weight

        # 按最终得分排序
        documents.sort(key=lambda x: x.score, reverse=True)

        return documents
