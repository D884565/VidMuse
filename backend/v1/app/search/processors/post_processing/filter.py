# backend/v1/app/search/processors/post_processing/filter.py
from typing import List, Dict, Any, Optional
import logging
from .base import BasePostProcessor
from ...core.models import SearchResult

logger = logging.getLogger(__name__)

class ResultFilter(BasePostProcessor):
    """结果过滤处理器，按规则过滤结果"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_score = self.config.get("min_score", 0.0)  # 最低得分阈值
        self.allowed_sources = self.config.get("allowed_sources")  # 允许的来源列表
        self.blocked_sources = self.config.get("blocked_sources", [])  # 禁止的来源列表
        self.filter_rules = self.config.get("filter_rules", {})  # 元数据过滤规则

    @property
    def processor_name(self) -> str:
        return "result_filter"

    async def _aprocess(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """异步过滤处理"""
        if not results:
            return []

        filtered = []
        for result in results:
            # 检查得分阈值
            if result.score < self.min_score:
                logger.debug(f"过滤结果[{result.result_id}]: 得分{result.score}低于阈值{self.min_score}")
                continue

            # 检查来源白名单
            if self.allowed_sources is not None and result.source not in self.allowed_sources:
                logger.debug(f"过滤结果[{result.result_id}]: 来源[{result.source}]不在白名单")
                continue

            # 检查来源黑名单
            if result.source in self.blocked_sources:
                logger.debug(f"过滤结果[{result.result_id}]: 来源[{result.source}]在黑名单")
                continue

            # 检查元数据过滤规则
            passed = True
            for key, expected_value in self.filter_rules.items():
                actual_value = result.metadata.get(key)
                if actual_value != expected_value:
                    logger.debug(f"过滤结果[{result.result_id}]: 元数据{key}={actual_value}不等于预期值{expected_value}")
                    passed = False
                    break

            if passed:
                filtered.append(result)

        logger.debug(f"过滤完成: 原始{len(results)}条，剩余{len(filtered)}条")
        return filtered
