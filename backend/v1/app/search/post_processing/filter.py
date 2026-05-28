from typing import List, Optional, Callable
from .base import BasePostProcessorImpl
from ..core import Query, Document

class Filter(BasePostProcessorImpl):
    """
    结果过滤器
    基于规则、阈值、黑名单等过滤不相关的结果
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.min_score_threshold = self.config.get("min_score_threshold", 0.6)
        self.blacklist_keywords = self.config.get("blacklist_keywords", [])
        self.custom_filters: List[Callable[[Document, Query], bool]] = []

    def add_filter(self, filter_func: Callable[[Document, Query], bool]) -> None:
        """添加自定义过滤函数，返回True表示保留该文档"""
        self.custom_filters.append(filter_func)

    def _process(self, documents: List[Document], query: Query) -> List[Document]:
        if not documents:
            return []

        filtered_docs = []

        for doc in documents:
            # 1. 分数阈值过滤
            if doc.score < self.min_score_threshold:
                continue

            # 2. 黑名单关键词过滤
            content_lower = doc.content.lower()
            has_blacklist_word = any(
                keyword.lower() in content_lower
                for keyword in self.blacklist_keywords
            )
            if has_blacklist_word:
                continue

            # 3. 自定义过滤规则
            passed_custom = all(
                filter_func(doc, query)
                for filter_func in self.custom_filters
            )
            if not passed_custom:
                continue

            # 所有过滤都通过
            filtered_docs.append(doc)

        return filtered_docs
