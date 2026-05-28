from typing import Optional
from .base import BaseQueryEnhancerImpl
from ..core import Query, SearchContext
from ..config import QUERY_ENHANCEMENT_CONFIG

class QueryRewriter(BaseQueryEnhancerImpl):
    """
    Query重写器
    优化用户查询表述，提高检索准确率
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config or QUERY_ENHANCEMENT_CONFIG)

        # 常见的查询优化规则，实际场景可以用LLM进行更智能的重写
        self.rewrite_rules = [
            # 去掉冗余的语气词
            (r"请问|麻烦问下|我想知道|能不能告诉我", ""),
            # 统一术语
            (r"AI|人工智能", "人工智能"),
            (r"大模型|LLM|大语言模型", "大语言模型"),
            (r"向量数据库|Milvus|Chroma|Pinecone", "向量数据库"),
        ]

    def _enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        import re

        original_text = query.text
        rewritten_text = original_text

        # 应用重写规则
        for pattern, replacement in self.rewrite_rules:
            rewritten_text = re.sub(pattern, replacement, rewritten_text)

        # 去除多余的空白字符
        rewritten_text = ' '.join(rewritten_text.split())

        # 如果重写后的文本和原始不同，更新查询
        if rewritten_text != original_text:
            query.enhanced_text = rewritten_text
            query.metadata["original_query"] = original_text
            query.metadata["rewritten"] = True
        else:
            query.metadata["rewritten"] = False

        return query
