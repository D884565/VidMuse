from typing import Optional
from .base import BaseQueryEnhancerImpl
from backend.v1.app.search.core import Query, SearchContext
from backend.v1.app.search.config import QUERY_ENHANCEMENT_CONFIG

class ContextProcessor(BaseQueryEnhancerImpl):
    """
    对话上下文处理器
    结合历史对话信息，补全当前查询的语义
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config or QUERY_ENHANCEMENT_CONFIG)
        self.max_history_turns = self.config.get("max_history_turns", 5)

    def _enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        if not context or not context.conversation_history:
            return query

        # 截取最近的对话历史
        recent_history = context.conversation_history[-self.max_history_turns:]

        # 构建上下文增强的查询文本
        context_text = ""
        for turn in recent_history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role and content:
                context_text += f"{role}: {content}\n"

        # 将上下文信息添加到query的metadata中
        query.metadata["conversation_context"] = context_text
        query.metadata["history_turns_used"] = len(recent_history)

        # 简单的上下文补全：如果查询很简短，结合历史上下文生成更完整的查询
        if len(query.text) < 10 and context_text:
            # 这里是基础实现，实际场景可以用LLM进行更智能的上下文补全
            enhanced_text = f"基于以下对话历史回答：{context_text}\n用户问题：{query.text}"
            query.enhanced_text = enhanced_text

        return query
