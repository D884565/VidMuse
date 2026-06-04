# backend/v1/app/search/processors/post_processing/merger.py
from typing import List, Dict, Any, Optional
import logging
from .base import BasePostProcessor
from ...core.models import SearchResult

logger = logging.getLogger(__name__)

class ResultMerger(BasePostProcessor):
    """结果合并处理器，合并相似或相关的结果"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.merge_similar = self.config.get("merge_similar", True)  # 是否合并相似结果

    @property
    def processor_name(self) -> str:
        return "result_merger"

    async def _aprocess(self, results: List[SearchResult], context: Dict[str, Any]) -> List[SearchResult]:
        """异步合并处理"""
        if not results:
            return []

        # 按来源分组，合并相同主题的结果
        merged_results = []
        content_groups: Dict[str, List[SearchResult]] = {}

        # 简单的分组（实际可以用聚类算法）
        for result in results:
            # 按内容前缀分组（示例逻辑）
            key = result.content[:20] if len(result.content) > 20 else result.content
            if key not in content_groups:
                content_groups[key] = []
            content_groups[key].append(result)

        # 合并每个组
        for key, group in content_groups.items():
            if len(group) == 1:
                merged_results.append(group[0])
                continue

            # 合并多个结果，保留得分最高的作为主结果
            main_result = max(group, key=lambda x: x.score)
            # 收集其他结果的信息
            other_sources = []
            other_contents = []
            for res in group:
                if res.result_id != main_result.result_id:
                    other_sources.append(res.source)
                    other_contents.append(res.content)

            # 更新主结果的元数据
            main_result.metadata["sources"] = list(set([res.source for res in group]))
            main_result.metadata["merged_count"] = len(group)
            if other_contents:
                main_result.metadata["additional_contents"] = other_contents

            merged_results.append(main_result)
            logger.debug(f"合并了{len(group)}条相似结果，主结果ID: {main_result.result_id}")

        logger.debug(f"合并完成: 原始{len(results)}条，剩余{len(merged_results)}条")
        return merged_results
