from typing import Dict, Any, Optional, List
from .base import BaseSearchTool
from ..core import Query, Document, SearchContext
from ..query_enhancement import ContextProcessor, IntentRecognizer, QueryRewriter, QueryExpander
from ..retrieval import VectorRetriever, KeywordRetriever, HybridRetriever, SQLRetriever, APIRetriever
from ..post_processing import Deduplicator, Filter, Merger, Reranker
from ..config import RETRIEVAL_CONFIG, QUERY_ENHANCEMENT_CONFIG, POST_PROCESSING_CONFIG, SUPPORTED_RETRIEVAL_TYPES
from ..core import RetrievalError


class GeneralSearchTool(BaseSearchTool):
    """
    通用检索工具，使用完整的RAG检索流程
    包含问题增强、意图识别、自动选择检索方式、结果后处理等完整流程
    适合普通的问答场景，不需要手动选择检索方式
    """

    @property
    def name(self) -> str:
        return "general_search"

    @property
    def description(self) -> str:
        return "通用智能检索，自动识别查询意图，选择最合适的检索方式。" \
               "包含完整的问题增强、检索、后处理流程。" \
               "适用于大多数普通问答场景，不需要手动指定检索方式。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户的查询问题"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的结果数量，默认10",
                    "default": 10
                },
                "retrieval_type": {
                    "type": "string",
                    "description": "强制指定检索类型，可选值：semantic, keyword, hybrid, sql, api，不指定则自动识别",
                    "enum": ["semantic", "keyword", "hybrid", "sql", "api"]
                }
            },
            "required": ["query"]
        }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.final_top_k = POST_PROCESSING_CONFIG.get("final_top_k", 10)

        # 初始化问题增强处理器
        self.query_enhancers = self._init_query_enhancers()

        # 初始化检索器
        self.retrievers = self._init_retrievers()

        # 初始化后处理器
        self.post_processors = self._init_post_processors()

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

    def execute(self, params: Dict[str, Any]) -> str:
        """执行通用检索"""
        query_text = params.get("query", "")
        top_k = params.get("top_k", self.default_top_k)
        retrieval_type = params.get("retrieval_type")

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type=retrieval_type,
                required_sources=[]
            )

            # 问题增强处理
            context = SearchContext()
            for enhancer in self.query_enhancers:
                query = enhancer.enhance(query, context)

            # 确定要使用的检索器
            retrieval_type = query.retrieval_type or "semantic"
            if retrieval_type not in SUPPORTED_RETRIEVAL_TYPES:
                retrieval_type = "semantic"

            retriever = self.retrievers.get(retrieval_type)
            if not retriever:
                raise RetrievalError(f"Unsupported retrieval type: {retrieval_type}")

            # 执行检索
            documents = retriever.retrieve(query, top_k * 2)  # 多查一些给后处理

            # 结果后处理
            for processor in self.post_processors:
                documents = processor.process(documents, query)

            # 截取最终结果数量
            final_documents = documents[:self.final_top_k]

            if not final_documents:
                return "未找到相关信息"

            # 格式化结果
            formatted_results = []
            for i, doc in enumerate(final_documents, 1):
                formatted_results.append(
                    f"[{i}] 得分: {doc.score:.2f}\n"
                    f"来源: {doc.source_type}\n"
                    f"内容: {doc.content}\n"
                )

            return f"检索完成，共找到{len(final_documents)}条相关信息：\n\n" + "\n---\n".join(formatted_results)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
