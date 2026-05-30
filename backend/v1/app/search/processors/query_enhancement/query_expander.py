from typing import Optional, List
from .base import BaseQueryEnhancerImpl
from backend.v1.app.search.core import Query, SearchContext
from backend.v1.app.search.config import QUERY_ENHANCEMENT_CONFIG

class QueryExpander(BaseQueryEnhancerImpl):
    """
    Query扩展器
    扩展查询相关的关键词和同义词，提高召回率
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config or QUERY_ENHANCEMENT_CONFIG)

        # 同义词词典，实际场景可以使用更大的同义词库或调用LLM生成
        self.synonym_dict = {
            "向量数据库": ["Milvus", "Chroma", "Pinecone", "向量检索库"],
            "大语言模型": ["LLM", "大模型", "GPT", "Claude", "文心一言", "通义千问"],
            "Python": ["py", "Python3", "Python编程"],
            "Java": ["Java编程", "JDK", "JVM"],
            "数据库": ["DB", "数据库系统", "数据存储"],
            "检索": ["搜索", "查询", "查找"],
        }

    def _enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        query_text = query.text
        expanded_keywords = set()

        # 提取关键词并扩展同义词
        for keyword, synonyms in self.synonym_dict.items():
            if keyword in query_text:
                expanded_keywords.add(keyword)
                expanded_keywords.update(synonyms)

        # 也可以加入原始查询中的分词结果作为关键词
        # 这里是简单实现，实际场景可以加入分词和关键词提取
        words = query_text.split()
        expanded_keywords.update(words)

        query.expanded_keywords = list(expanded_keywords)
        query.metadata["expanded_keywords_count"] = len(expanded_keywords)

        return query
