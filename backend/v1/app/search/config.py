from typing import Dict, Any, List

# 数据源配置
DATA_SOURCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "milvus": {
        "host": "localhost",
        "port": 19530,
        "default_collection": "documents"
    },
    "elasticsearch": {
        "host": "localhost",
        "port": 9200,
        "default_index": "documents"
    },
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "vidmuse"
    }
}

# 检索配置
RETRIEVAL_CONFIG: Dict[str, Any] = {
    "default_top_k": 10,
    "min_score_threshold": 0.6,  # 最低相似度阈值
    "max_query_length": 512,     # 查询最大长度
    "parallel_retrieval": True,  # 是否并行检索多个数据源
    "retrieval_timeout": 10      # 检索超时时间（秒）
}

# 问题增强配置
QUERY_ENHANCEMENT_CONFIG: Dict[str, Any] = {
    "enable_context_processing": True,
    "enable_intent_recognition": True,
    "enable_query_rewrite": True,
    "enable_query_expansion": True,
    "max_history_turns": 5  # 最多使用的历史对话轮数
}

# 后处理配置
POST_PROCESSING_CONFIG: Dict[str, Any] = {
    "enable_deduplication": True,
    "enable_filtering": True,
    "enable_merging": True,
    "enable_reranking": True,
    "deduplication_field": "id",  # 去重字段
    "rerank_top_k": 20,  # 重排序的候选数量
    "final_top_k": 10    # 最终返回结果数量
}

# 支持的数据源类型
SUPPORTED_SOURCES: List[str] = ["vector", "keyword", "sql", "api"]

# 支持的检索方式
SUPPORTED_RETRIEVAL_TYPES: List[str] = ["semantic", "keyword", "hybrid", "sql"]
