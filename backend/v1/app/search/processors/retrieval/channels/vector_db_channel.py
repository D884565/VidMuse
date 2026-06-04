# backend/v1/app/search/processors/retrieval/channels/vector_db_channel.py
from typing import List, Optional, Dict, Any
import logging
from ....core.interfaces import SearchChannel
from ....core.models import SearchQuery, SearchResult
from backend.store.vector import get_vector_db_client

logger = logging.getLogger(__name__)

class VectorDBChannel(SearchChannel):
    """向量数据库检索渠道"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化向量数据库渠道
        :param config: 渠道配置
        """
        self.config = config
        self.collection_name = config["collection"]
        self.weight = config.get("weight", 1.0)
        self.vector_client = get_vector_db_client(self.collection_name)

    @property
    def channel_name(self) -> str:
        return "vector_db"

    @property
    def channel_type(self) -> str:
        return "vector_db"

    def search(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """同步检索"""
        if not query.query_embedding:
            logger.warning("查询向量为空，无法进行向量检索")
            return []

        try:
            # 调用向量数据库查询
            results = self.vector_client.query_similar(
                query_embeddings=[query.query_embedding],
                n_results=query.top_k,
                where=query.filters
            )

            # 转换为统一结果格式
            return self._convert_to_search_results(results)
        except Exception as e:
            logger.error(f"向量数据库检索失败: {str(e)}", exc_info=True)
            return []

    async def asearch(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """异步检索（向量数据库客户端目前是同步的，这里用线程池包装）"""
        import asyncio
        return await asyncio.to_thread(self.search, query, context)

    def health_check(self) -> bool:
        """健康检查"""
        try:
            stats = self.vector_client.get_collection_stats()
            return stats is not None
        except Exception as e:
            logger.error(f"向量数据库健康检查失败: {str(e)}")
            return False

    def _convert_to_search_results(self, raw_results: Dict) -> List[SearchResult]:
        """
        将向量数据库原始结果转换为统一的SearchResult格式
        :param raw_results: 向量数据库返回的原始结果
        :return: SearchResult列表
        """
        results = []
        if not raw_results or "ids" not in raw_results or not raw_results["ids"]:
            return results

        ids = raw_results["ids"][0]
        distances = raw_results["distances"][0]
        metadatas = raw_results["metadatas"][0]
        documents = raw_results["documents"][0]

        for i in range(len(ids)):
            # 距离转得分（距离越小得分越高，归一化到0-1）
            score = max(0.0, 1.0 - float(distances[i])) * self.weight

            result = SearchResult(
                result_id=str(ids[i]),
                content=str(documents[i]),
                score=score,
                source=self.channel_name,
                source_type=metadatas[i].get("type", "unknown") if metadatas[i] else "unknown",
                metadata=metadatas[i] or {}
            )
            results.append(result)

        return results
