# backend/v1/app/search/processors/query_enhancement/context_processor.py
from typing import Dict, Any, List
import logging
from .base import BaseQueryProcessor
from ...core.models import SearchQuery

logger = logging.getLogger(__name__)

class ContextProcessor(BaseQueryProcessor):
    """上下文处理器，结合会话历史补全查询"""

    @property
    def processor_name(self) -> str:
        return "context_processor"

    async def _aprocess(self, query: SearchQuery, context: Dict[str, Any]) -> SearchQuery:
        """
        异步处理上下文，补全查询
        示例实现：简单的上下文补全，实际项目中可接入LLM进行上下文理解
        """
        session_context = query.metadata.get("session_context", [])
        if not session_context:
            return query

        # 简单的上下文补全规则：如果查询包含指代，补充上文提到的实体
        query_text = query.query_text
        if any(pronoun in query_text for pronoun in ["它", "这个", "那个", "这款", "那款"]):
            # 提取上文提到的实体（简单示例，只取最后一个用户问题）
            last_user_message = next(
                (msg["content"] for msg in reversed(session_context) if msg["role"] == "user"),
                ""
            )

            if last_user_message:
                # 简单的实体提取（实际应该用NER）
                entities = []
                entity_keywords = ["手机", "电脑", "产品", "设备", "功能", "服务"]
                for kw in entity_keywords:
                    if kw in last_user_message:
                        entities.append(kw)

                if entities:
                    # 补充到查询中
                    entity_str = " ".join(entities)
                    original_query = query_text
                    query_text = query_text.replace("它", entity_str)\
                                         .replace("这个", entity_str)\
                                         .replace("那个", entity_str)\
                                         .replace("这款", entity_str)\
                                         .replace("那款", entity_str)

                    if query_text != original_query:
                        logger.debug(f"上下文补全: '{original_query}' -> '{query_text}'")
                        query.query_text = query_text

        return query
