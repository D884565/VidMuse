from typing import List, Optional
from .base import BaseRetrieverImpl
from backend.v1.app.search.core import Query, Document
from .channels.http_api_channel import HttpAPIChannel

class APIRetriever(BaseRetrieverImpl):
    """
    API检索器
    调用外部API进行检索
    """

    def __init__(self, config: Optional[dict] = None, channel: Optional[HttpAPIChannel] = None):
        super().__init__(config)
        self.channel = channel or HttpAPIChannel(config)

    def _retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        # 这里是模拟实现，实际需要调用外部API

        mock_documents = []
        for i in range(min(top_k, 2)):
            mock_documents.append(Document(
                id=f"api_doc_{i}",
                content=f"外部API返回的结果：{query.text}相关信息{i}",
                score=0.75,
                source="api",
                source_type="external_api",
                metadata={"api_endpoint": "https://api.example.com/search", "query": query.text}
            ))

        return mock_documents
