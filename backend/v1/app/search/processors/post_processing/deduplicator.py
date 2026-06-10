# backend/v1/app/search/processors/post_processing/deduplicator.py
from typing import List, Dict, Any, Optional
import logging
from hashlib import md5
from .base import BasePostProcessor
from ...core.models import SearchResult

logger = logging.getLogger(__name__)

class Deduplicator(BasePostProcessor):
    """结果去重处理器，基于内容哈希去重"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # 相似度阈值（0-1），高于此值认为重复
        self.similarity_threshold = self.config.get("similarity_threshold", 0.95)

    @property
    def processor_name(self) -> str:
        return "deduplicator"

    async def _aprocess(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """异步去重处理"""
        if not results:
            return []

        # 基于内容哈希去重，保留得分最高的
        content_map: Dict[str, SearchResult] = {}

        for result in results:
            # 计算内容哈希
            content_hash = self._calculate_content_hash(result.content)

            if content_hash not in content_map:
                content_map[content_hash] = result
            else:
                # 保留得分更高的
                existing = content_map[content_hash]
                if result.score > existing.score:
                    # 记录来源信息
                    if "duplicate_sources" not in result.metadata:
                        result.metadata["duplicate_sources"] = []
                    result.metadata["duplicate_sources"].append({
                        "source": existing.source,
                        "score": existing.score,
                        "result_id": existing.result_id
                    })
                    content_map[content_hash] = result
                    logger.debug(f"去重: 内容重复，保留得分更高的[{result.result_id}]，丢弃[{existing.result_id}]")

        unique_results = list(content_map.values())
        logger.debug(f"去重完成: 原始{len(results)}条，剩余{len(unique_results)}条")

        return unique_results

    def _calculate_content_hash(self, content: str) -> str:
        """计算内容哈希，用于去重"""
        # 简单的哈希计算，实际可以用SimHash等算法支持相似内容去重
        content_clean = content.strip().lower()
        return md5(content_clean.encode("utf-8")).hexdigest()
