from typing import List, Optional, Set
from .base import BasePostProcessorImpl
from backend.v1.app.search.core import Query, Document

class Deduplicator(BasePostProcessorImpl):
    """
    结果去重器
    移除重复的检索结果
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.deduplication_field = self.config.get("deduplication_field", "id")

    def _process(self, documents: List[Document], query: Query) -> List[Document]:
        if not documents:
            return []

        seen_ids: Set[str] = set()
        unique_docs = []

        for doc in documents:
            # 获取去重字段的值
            doc_id = getattr(doc, self.deduplication_field, None)
            if doc_id is None:
                # 如果没有指定字段，用内容哈希作为标识
                doc_id = hash(doc.content)

            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_docs.append(doc)

        return unique_docs
