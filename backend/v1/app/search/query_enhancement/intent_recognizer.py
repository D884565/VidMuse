from typing import Optional, Dict, List
from .base import BaseQueryEnhancerImpl
from ..core import Query, SearchContext
from ..config import QUERY_ENHANCEMENT_CONFIG, SUPPORTED_RETRIEVAL_TYPES

class IntentRecognizer(BaseQueryEnhancerImpl):
    """
    查询意图识别器
    识别用户查询的意图，确定最合适的检索方式和数据源
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config or QUERY_ENHANCEMENT_CONFIG)

        # 意图关键词映射，实际场景可以用LLM或训练好的分类模型
        self.intent_keywords: Dict[str, List[str]] = {
            "semantic_search": [
                "什么是", "怎么", "如何", "为什么", "解释", "介绍", "详细说明",
                "概念", "定义", "原理", "方法", "步骤", "教程"
            ],
            "keyword_search": [
                "找", "搜索", "查询", "查找", "有没有", "哪些", "列表", "所有",
                "包含", "包括", "有关", "相关"
            ],
            "sql_query": [
                "统计", "总数", "多少个", "平均值", "最大值", "最小值", "总和",
                "排名", "排序", "分组", "筛选", "条件"
            ],
            "api_call": [
                "调用", "接口", "API", "服务", "第三方", "外部"
            ]
        }

        # 意图到检索类型的映射
        self.intent_to_retrieval_type: Dict[str, str] = {
            "semantic_search": "semantic",
            "keyword_search": "keyword",
            "sql_query": "sql",
            "api_call": "api"
        }

    def _enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        # 如果已经指定了检索类型，不需要再识别
        if query.retrieval_type and query.retrieval_type in SUPPORTED_RETRIEVAL_TYPES:
            return query

        query_text = query.text.lower()
        intent_scores: Dict[str, int] = {}

        # 关键词匹配得分
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in query_text)
            if score > 0:
                intent_scores[intent] = score

        if intent_scores:
            # 选择得分最高的意图
            max_score = max(intent_scores.values())
            top_intents = [intent for intent, score in intent_scores.items() if score == max_score]
            primary_intent = top_intents[0]

            query.intent = primary_intent
            query.retrieval_type = self.intent_to_retrieval_type.get(primary_intent, "semantic")
            query.metadata["intent_scores"] = intent_scores
        else:
            # 默认语义检索
            query.intent = "semantic_search"
            query.retrieval_type = "semantic"
            query.metadata["intent_scores"] = {}

        return query
