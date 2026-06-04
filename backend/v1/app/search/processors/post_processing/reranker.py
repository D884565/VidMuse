# backend/v1/app/search/processors/post_processing/reranker.py
from typing import List, Dict, Any, Optional
import logging
from .base import BasePostProcessor
from ...core.models import SearchResult

logger = logging.getLogger(__name__)

class Reranker(BasePostProcessor):
    """结果重排序处理器，重新计算得分并排序"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # 来源权重配置
        self.source_weights = self.config.get("source_weights", {
            "vector_db": 1.0,
            "mysql": 0.9,
            "http_api": 0.8
        })
        self.top_k = self.config.get("top_k")  # 返回前K个结果

    @property
    def processor_name(self) -> str:
        return "reranker"

    async def _aprocess(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """异步重排序处理"""
        if not results:
            return []

        # 重新计算得分
        for result in results:
            # 应用来源权重
            source_weight = self.source_weights.get(result.source, 1.0)
            result.score = result.score * source_weight

            # 新鲜度加权（如果有创建时间）
            if "created_at" in result.metadata:
                # 可以根据时间衰减得分
                pass

        # 按得分降序排序
        results.sort(key=lambda x: x.score, reverse=True)

        # 限制返回数量
        if self.top_k and len(results) > self.top_k:
            results = results[:self.top_k]
            logger.debug(f"重排序后截断到前{self.top_k}条结果")

        logger.debug(f"重排序完成")
        return results
