# backend/v1/app/search/processors/query_enhancement/query_rewriter.py
from typing import Dict, Any
import logging
from .base import BaseQueryProcessor
from ...core.models import SearchQuery

logger = logging.getLogger(__name__)

class QueryRewriter(BaseQueryProcessor):
    """查询重写处理器，优化查询表述"""

    @property
    def processor_name(self) -> str:
        return "query_rewriter"

    async def _aprocess(self, query: SearchQuery, context: Dict[str, Any]) -> SearchQuery:
        """
        异步重写查询
        示例实现：简单的关键词替换和优化，实际项目中可接入LLM进行智能重写
        """
        original_query = query.query_text
        rewritten_query = original_query

        # 简单的重写规则示例
        rewrite_rules = [
            ("我忘记密码了", "如何重置密码"),
            ("密码忘记了", "如何重置密码"),
            ("密码忘了", "如何重置密码"),
            ("怎么改密码", "如何修改密码"),
            ("怎么用", "使用方法"),
            ("多少钱", "价格是多少"),
        ]

        for old, new in rewrite_rules:
            if old in rewritten_query:
                rewritten_query = rewritten_query.replace(old, new)

        # 如果查询太短，添加通用关键词
        if len(rewritten_query) < 5:
            rewritten_query = f"{rewritten_query} 怎么用 说明"

        if rewritten_query != original_query:
            logger.debug(f"查询重写: '{original_query}' -> '{rewritten_query}'")
            query.query_text = rewritten_query

        return query
