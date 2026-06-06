# 多通道检索引擎包
"""
多通道检索引擎，支持向量库、MySQL、HTTP API等多种检索渠道，
提供查询增强、并发检索、结果后处理等完整功能。
"""

from .search_engine import SearchEngine
from .core.models import SearchQuery, SearchResult
from .config import SearchConfig
from .core.exceptions import SearchError, ChannelTimeoutError, ProcessorError

__all__ = [
    "SearchEngine",
    "SearchQuery",
    "SearchResult",
    "SearchConfig",
    "SearchError",
    "ChannelTimeoutError",
    "ProcessorError"
]
