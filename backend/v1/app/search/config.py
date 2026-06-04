# backend/v1/app/search/config.py
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from backend.v1.app.config.config import settings

@dataclass
class SearchConfig:
    """检索模块配置"""

    # 全局配置
    DEFAULT_TOP_K: int = 10
    DEFAULT_TIMEOUT: int = 30
    FAIL_FAST: bool = False  # 是否快速失败，False表示部分失败也继续

    # 启用的检索渠道
    ENABLED_CHANNELS: List[str] = field(default_factory=lambda: ["vector_db", "mysql", "http_api"])

    # 各渠道配置
    CHANNEL_CONFIG: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "vector_db": {
            "enabled": True,
            "timeout": 10,
            "collection": settings.CHROMADB_PRODUCT_COLLECTION,
            "weight": 1.0
        },
        "mysql": {
            "enabled": True,
            "timeout": 5,
            "table": "product_info",
            "search_fields": ["name", "description"],
            "source_type": "product",
            "weight": 0.8
        },
        "http_api": {
            "enabled": False,  # 默认不启用
            "timeout": 15,
            "endpoint": "",
            "api_key": "",
            "weight": 0.7
        }
    })

    # 启用的查询增强处理器（按执行顺序）
    ENABLED_QUERY_PROCESSORS: List[str] = field(default_factory=lambda: [
        "context_processor",
        "query_rewriter",
        "intent_recognizer"
    ])

    # 启用的后处理器（按执行顺序）
    ENABLED_POST_PROCESSORS: List[str] = field(default_factory=lambda: [
        "result_filter",
        "deduplicator",
        "result_merger",
        "reranker"
    ])

    # 后处理器配置
    POST_PROCESSOR_CONFIG: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "result_filter": {
            "min_score": 0.3,
            "filter_rules": {}
        },
        "deduplicator": {
            "similarity_threshold": 0.95
        },
        "reranker": {
            "top_k": 10
        }
    })

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "SearchConfig":
        """从字典创建配置实例"""
        config = cls()
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith("_")
        }
