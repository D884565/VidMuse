# backend/v1/app/search/processors/query_enhancement/intent_recognizer.py
from typing import Dict, Any
import logging
from .base import BaseQueryProcessor
from ...core.models import SearchQuery

logger = logging.getLogger(__name__)

class IntentRecognizer(BaseQueryProcessor):
    """意图识别处理器，识别用户查询意图"""

    @property
    def processor_name(self) -> str:
        return "intent_recognizer"

    async def _aprocess(self, query: SearchQuery, context: Dict[str, Any]) -> SearchQuery:
        """
        异步识别查询意图
        示例实现：简单的关键词匹配，实际项目中可接入分类模型或LLM
        """
        query_text = query.query_text.lower()
        intent = "general"

        # 简单的意图规则示例
        intent_rules = {
            "password_reset": ["密码", "重置", "忘记", "找回"],
            "price_query": ["价格", "多少钱", "售价", "费用"],
            "usage_guide": ["怎么用", "使用", "操作", "教程", "说明"],
            "troubleshooting": ["故障", "报错", "问题", "不工作", "坏了"],
            "feature_query": ["功能", "支持", "有什么", "特性"],
        }

        max_matches = 0
        for intent_name, keywords in intent_rules.items():
            matches = sum(1 for kw in keywords if kw in query_text)
            if matches > max_matches:
                max_matches = matches
                intent = intent_name

        logger.debug(f"识别查询意图: '{query_text}' -> {intent}")
        query.metadata["intent"] = intent

        # 根据意图添加过滤条件
        if intent == "password_reset":
            query.filters["type"] = query.filters.get("type", []) + ["faq", "troubleshooting"]

        return query
