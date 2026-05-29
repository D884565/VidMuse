from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..core import Query, Document, SearchContext
from ..query_enhancement import ContextProcessor, IntentRecognizer, QueryRewriter, QueryExpander
from ..retrieval import VectorRetriever, KeywordRetriever, HybridRetriever, SQLRetriever, APIRetriever
from ..post_processing import Deduplicator, Filter, Merger, Reranker
from ..config import (
    RETRIEVAL_CONFIG,
    QUERY_ENHANCEMENT_CONFIG,
    POST_PROCESSING_CONFIG,
    SUPPORTED_RETRIEVAL_TYPES
)
import json


class BaseSearchTool(ABC):
    """
    检索工具抽象基类，所有检索工具必须继承此类
    提供统一的检索流程模板，子类只需实现特定逻辑
    """

    # 工具基础配置，子类可覆盖
    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.final_top_k = POST_PROCESSING_CONFIG.get("final_top_k", 10)
        self.min_score_threshold = RETRIEVAL_CONFIG.get("min_score_threshold", 0.6)

        # 初始化公共组件（所有工具复用相同的组件实例）
        self.query_enhancers = self._init_query_enhancers()
        self.retrievers = self._init_retrievers()
        self.post_processors = self._init_post_processors()

    def _init_query_enhancers(self) -> List[Any]:
        """初始化问题增强处理器链，子类可自定义"""
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
        """初始化检索器实例，所有工具共享"""
        return {
            "semantic": VectorRetriever(),
            "keyword": KeywordRetriever(),
            "hybrid": HybridRetriever(),
            "sql": SQLRetriever(),
            "api": APIRetriever()
        }

    def _init_post_processors(self) -> List[Any]:
        """初始化后处理器链，子类可自定义"""
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

    def enhance_query(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        """统一的查询增强流程，子类可重写"""
        context = context or SearchContext()
        for enhancer in self.query_enhancers:
            query = enhancer.enhance(query, context)
        return query

    def retrieve_documents(self, query: Query, top_k: int = 10) -> List[Document]:
        """统一的检索流程，子类可重写"""
        retrieval_type = query.retrieval_type or self.default_retrieval_type
        if retrieval_type not in SUPPORTED_RETRIEVAL_TYPES:
            retrieval_type = self.default_retrieval_type

        retriever = self.retrievers.get(retrieval_type)
        if not retriever:
            raise ValueError(f"Unsupported retrieval type: {retrieval_type}")

        # 多查一些给后处理
        return retriever.retrieve(query, top_k * 2)

    def process_results(self, documents: List[Document], query: Query) -> List[Document]:
        """统一的结果后处理流程，子类可重写"""
        for processor in self.post_processors:
            documents = processor.process(documents, query)

        # 过滤低得分结果
        documents = [doc for doc in documents if doc.score >= self.min_score_threshold]

        # 截取最终结果数量
        return documents[:self.final_top_k]

    def format_results(self, documents: List[Document]) -> str:
        """统一的结果格式化，子类可重写"""
        if not documents:
            return "未找到相关信息"

        formatted_results = []
        for i, doc in enumerate(documents, 1):
            source_info = f"来源: {doc.source_type}"
            if doc.metadata.get("collection"):
                source_info += f", 集合: {doc.metadata['collection']}"

            formatted_results.append(
                f"[{i}] 得分: {doc.score:.2f}\n"
                f"{source_info}\n"
                f"内容: {doc.content}\n"
            )

        return f"检索完成，共找到{len(documents)}条相关信息：\n\n" + "\n---\n".join(formatted_results)

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> str:
        """
        执行工具逻辑，子类必须实现
        :param params: 工具参数，根据parameters_schema验证后的参数
        :return: 工具执行结果，字符串格式
        """
        pass

    def get_function_definition(self) -> Dict[str, Any]:
        """转换为大模型function calling所需的格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """
        验证参数是否符合schema定义
        简单实现，复杂场景可以使用jsonschema库
        """
        # 简单验证必填参数
        if "required" in self.parameters_schema:
            for required_param in self.parameters_schema["required"]:
                if required_param not in params:
                    return False
        return True
