from typing import List, Optional
from .base import BaseRetrieverImpl
from backend.v1.app.search.core import Query, Document
from .channels.chromadb_channel import ChromaDBChannel
from backend.v1.app.search.config import DATA_SOURCE_CONFIG


class ChromaDBRetriever(BaseRetrieverImpl):
    """
    ChromaDB向量数据库检索器
    基于向量相似度的语义检索
    """

    def __init__(self, config: Optional[dict] = None, channel: Optional[ChromaDBChannel] = None):
        super().__init__(config)
        self.channel = channel or ChromaDBChannel(DATA_SOURCE_CONFIG.get("chromadb", {}))

    def _retrieve(self, query: Query, top_k: int = 10) -> List[Document]:
        # 使用增强后的查询文本，如果没有则用原始文本
        query_text = query.enhanced_text or query.text

        # 这里是模拟实现，实际需要调用ChromaDB通道
        # 实际场景：1. 对query_text进行向量化 2. 调用chromadb通道查询 3. 转换为Document对象

        # 模拟返回结果
        mock_documents = []
        for i in range(min(top_k, 5)):
            mock_documents.append(Document(
                id=f"chroma_doc_{i}",
                content=f"这是和'{query_text}'相关的ChromaDB检索结果文档{i}",
                score=0.87 - i * 0.04,
                source="vector",
                source_type="chromadb",
                metadata={"collection": "documents"}
            ))

        return mock_documents
