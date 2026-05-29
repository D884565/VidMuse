import time
from typing import Optional, List, Dict, Any
from ..core import Query, Document, SearchContext, SearchResult, RetrievalError
from ..query_enhancement import (
    ContextProcessor,
    IntentRecognizer,
    QueryRewriter,
    QueryExpander
)
from ..retrieval import (
    VectorRetriever,
    KeywordRetriever,
    HybridRetriever,
    SQLRetriever,
    APIRetriever
)
from ..post_processing import (
    Deduplicator,
    Filter,
    Merger,
    Reranker
)
from ..config import (
    RETRIEVAL_CONFIG,
    QUERY_ENHANCEMENT_CONFIG,
    POST_PROCESSING_CONFIG,
    SUPPORTED_RETRIEVAL_TYPES
)
from ..tools import (
    BaseSearchTool,
    ALL_TOOLS
)

class SearchService:
    """
    统一检索服务类
    编排完整的检索流程：问题增强 -> 检索执行 -> 结果后处理
    重构版本：支持工具化调用，保持向下兼容
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # 初始化问题增强处理器（保留原有逻辑，兼容现有代码）
        self.query_enhancers = self._init_query_enhancers()

        # 初始化检索器（保留原有逻辑，兼容现有代码）
        self.retrievers = self._init_retrievers()

        # 初始化后处理器（保留原有逻辑，兼容现有代码）
        self.post_processors = self._init_post_processors()

        # 配置
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.final_top_k = POST_PROCESSING_CONFIG.get("final_top_k", 10)

    @staticmethod
    def get_all_tools() -> List[BaseSearchTool]:
        """获取所有可用的检索工具实例，方便Agent系统集成"""
        return [tool_cls() for tool_cls in ALL_TOOLS]

    @staticmethod
    def get_tool_by_name(name: str) -> Optional[BaseSearchTool]:
        """根据工具名称获取工具实例"""
        for tool_cls in ALL_TOOLS:
            tool = tool_cls()
            if tool.name == name:
                return tool
        return None

    def _init_query_enhancers(self) -> List[Any]:
        """初始化问题增强处理器链"""
        enhancers = []
        config = QUERY_ENHANCEMENT_CONFIG

        if config.get("enable_context_processing", True):
            enhancers.append(ContextProcessor())
        if config.get("enable_intent_recognition", True):
            enhancers.append(IntentRecognizer())
        if config.get("enable_query_rewrite", True):
            enhancers.append(QueryRewriter())
        if config.get("enable_query_expansion", True):
            enhancers.append(QueryExpander())

        return enhancers

    def _init_retrievers(self) -> Dict[str, Any]:
        """初始化各种检索器"""
        return {
            "semantic": VectorRetriever(),
            "keyword": KeywordRetriever(),
            "hybrid": HybridRetriever(),
            "sql": SQLRetriever(),
            "api": APIRetriever()
        }

    def _init_post_processors(self) -> List[Any]:
        """初始化后处理器链"""
        processors = []
        config = POST_PROCESSING_CONFIG

        if config.get("enable_deduplication", True):
            processors.append(Deduplicator())
        if config.get("enable_filtering", True):
            processors.append(Filter())
        if config.get("enable_merging", True):
            processors.append(Merger())
        if config.get("enable_reranking", True):
            processors.append(Reranker())

        return processors

    def search(
        self,
        query_text: str,
        context: Optional[SearchContext] = None,
        retrieval_type: Optional[str] = None,
        required_sources: Optional[List[str]] = None,
        top_k: Optional[int] = None
    ) -> SearchResult:
        """
        执行完整的检索流程

        :param query_text: 用户查询文本
        :param context: 检索上下文
        :param retrieval_type: 强制指定检索类型（semantic/keyword/hybrid/sql/api）
        :param required_sources: 强制指定检索的数据源
        :param top_k: 返回结果数量
        :return: 检索结果
        """
        start_time = time.time()
        context = context or SearchContext()
        top_k = top_k or context.top_k or self.default_top_k

        try:
            # 1. 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type=retrieval_type,
                required_sources=required_sources or []
            )

            # 2. 问题增强处理
            for enhancer in self.query_enhancers:
                query = enhancer.enhance(query, context)

            # 3. 确定要使用的检索器
            retrieval_type = query.retrieval_type or "semantic"
            if retrieval_type not in SUPPORTED_RETRIEVAL_TYPES:
                retrieval_type = "semantic"

            retriever = self.retrievers.get(retrieval_type)
            if not retriever:
                raise RetrievalError(f"Unsupported retrieval type: {retrieval_type}")

            # 4. 执行检索
            documents = retriever.retrieve(query, top_k * 2)  # 多查一些给后处理

            # 5. 结果后处理
            for processor in self.post_processors:
                documents = processor.process(documents, query)

            # 6. 截取最终结果数量
            final_documents = documents[:self.final_top_k]

            # 7. 构建返回结果
            cost_time = time.time() - start_time
            return SearchResult(
                query=query,
                documents=final_documents,
                context=context,
                cost_time=cost_time,
                success=True,
                retrieval_metadata={
                    "retrieval_type": retrieval_type,
                    "retrieved_count": len(documents),
                    "final_count": len(final_documents)
                }
            )

        except Exception as e:
            cost_time = time.time() - start_time
            return SearchResult(
                query=Query(text=query_text),
                documents=[],
                context=context,
                cost_time=cost_time,
                success=False,
                error_msg=str(e)
            )

    async def async_search(
        self,
        query_text: str,
        context: Optional[SearchContext] = None,
        retrieval_type: Optional[str] = None,
        required_sources: Optional[List[str]] = None,
        top_k: Optional[int] = None
    ) -> SearchResult:
        """异步版本的检索接口，实际场景可实现并行检索"""
        # 这里直接调用同步版本，实际场景可以改造为异步实现
        return self.search(query_text, context, retrieval_type, required_sources, top_k)
