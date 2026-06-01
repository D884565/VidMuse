from .core import (
    Query,
    Document,
    SearchContext,
    SearchResult,
    BaseQueryEnhancer,
    BaseRetriever,
    BasePostProcessor,
    BaseDataSourceChannel,
    SearchBaseException,
    QueryEnhancementError,
    RetrievalError,
    PostProcessingError,
    ConfigurationError,
    DataSourceError,
    ComponentRegistry,
    component_registry
)
from .processors.query_enhancement import (
    ContextProcessor,
    IntentRecognizer,
    QueryRewriter,
    QueryExpander
)
from .processors.retrieval import (
    VectorRetriever,
    ChromaDBRetriever,
    KeywordRetriever,
    HybridRetriever,
    SQLRetriever,
    APIRetriever
)
from .processors.retrieval.channels import (
    MilvusChannel,
    ESChannel,
    MySQLChannel,
    HttpAPIChannel,
    ChromaDBChannel
)
from .processors.post_processing import (
    Deduplicator,
    Filter,
    Merger,
    Reranker
)
from .config import (
    DATA_SOURCE_CONFIG,
    RETRIEVAL_CONFIG,
    QUERY_ENHANCEMENT_CONFIG,
    POST_PROCESSING_CONFIG,
    SUPPORTED_SOURCES,
    SUPPORTED_RETRIEVAL_TYPES
)
from .tools import (
    BaseSearchTool,
    SemanticSearchTool,
    KeywordSearchTool,
    SQLQueryTool,
    HybridSearchTool,
    GeneralSearchTool,
    ALL_TOOLS
)

# 初始化组件注册中心，自动发现所有组件（必须在创建Agent之前调用）
component_registry.auto_discover()

from backend.v1.app.rag_trace.dao import AgentTraceDAO, agent_trace_dao


__version__ = "1.0.0"

__all__ = [
    # Core
    "Query",
    "Document",
    "SearchContext",
    "SearchResult",
    "BaseQueryEnhancer",
    "BaseRetriever",
    "BasePostProcessor",
    "BaseDataSourceChannel",
    "SearchBaseException",
    "QueryEnhancementError",
    "RetrievalError",
    "PostProcessingError",
    "ConfigurationError",
    "DataSourceError",
    "ComponentRegistry",
    "component_registry",

    # Query Enhancement
    "ContextProcessor",
    "IntentRecognizer",
    "QueryRewriter",
    "QueryExpander",

    # Retrieval
    "VectorRetriever",
    "ChromaDBRetriever",
    "KeywordRetriever",
    "HybridRetriever",
    "SQLRetriever",
    "APIRetriever",

    # Data Source Channels
    "MilvusChannel",
    "ESChannel",
    "MySQLChannel",
    "HttpAPIChannel",
    "ChromaDBChannel",

    # Post Processing
    "Deduplicator",
    "Filter",
    "Merger",
    "Reranker",


    # Tools
    "BaseSearchTool",
    "SemanticSearchTool",
    "KeywordSearchTool",
    "SQLQueryTool",
    "HybridSearchTool",
    "GeneralSearchTool",
    "ALL_TOOLS",

    # Config
    "DATA_SOURCE_CONFIG",
    "RETRIEVAL_CONFIG",
    "QUERY_ENHANCEMENT_CONFIG",
    "POST_PROCESSING_CONFIG",
    "SUPPORTED_SOURCES",
    "SUPPORTED_RETRIEVAL_TYPES",


    # 组件注册中心
    "ComponentRegistry",
    "component_registry",
]
