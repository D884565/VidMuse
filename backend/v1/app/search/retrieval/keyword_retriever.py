from typing import List, Optional
from .base import BaseRetrieverImpl
from ..core import Query, Document
from .channels.es_channel import ESChannel
from ..config import DATA_SOURCE_CONFIG

class KeywordRetriever(BaseRetrieverImpl):
    """
    关键词检索器
    基于全文索引的关键词检索
    """

    def __init__(self, config: Optional[dict] = None, channel: Optional[ESChannel] = None):
        super().__init__(config)
        self.channel = channel or ESChannel(DATA_SOURCE_CONFIG.get("elasticsearch", {}))

    def _retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        # 使用扩展的关键词进行检索，如果没有则用原始文本
        search_terms = query.expanded_keywords or [query.text]
        search_query = ' '.join(search_terms)

        # 这里是模拟实现，实际需要调用ES通道

        mock_documents = []
        for i in range(min(top_k, 5)):
            mock_documents.append(Document(
                id=f"kw_doc_{i}",
                content=f"这是包含关键词'{search_query}'的检索结果文档{i}",
                score=0.8 - i * 0.06,
                source="keyword",
                source_type="elasticsearch",
                metadata={"index": "documents", "matched_keywords": search_terms}
            ))

        return mock_documents
