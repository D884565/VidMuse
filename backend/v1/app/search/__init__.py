# backend/v1/app/search/__init__.py
"""
多通道检索模块
支持多种检索渠道，提供统一的检索接口
"""

from .search_engine import SearchEngine
from .core.models import SearchQuery, SearchResult
from .core.exceptions import (
    SearchError, ChannelError, ChannelTimeoutError,
    ProcessorError, QueryValidationError
)
from .config import SearchConfig

__all__ = [
    "SearchEngine",
    "SearchQuery",
    "SearchResult",
    "SearchConfig",
    "SearchError",
    "ChannelError",
    "ChannelTimeoutError",
    "ProcessorError",
    "QueryValidationError",
]

# 版本信息
__version__ = "1.0.0"
