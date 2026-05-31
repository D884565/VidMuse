from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..core import Query, Document, SearchContext, component_registry
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
    支持可插拔组件编排，子类可以通过配置选择要使用的组件
    """

    # 工具基础配置，子类可覆盖
    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    # 组件配置，子类可以自定义使用哪些组件
    # 格式：["组件名称1", "组件名称2"] 或者 [("组件名称1", 配置字典), ("组件名称2", 配置字典)]
    query_enhancer_config: List[Any] = []
    retriever_config: Dict[str, Any] = {}  # key: 检索器别名, value: (组件名称, 配置字典)
    post_processor_config: List[Any] = []

    # 默认检索类型
    default_retrieval_type: str = "semantic"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.final_top_k = POST_PROCESSING_CONFIG.get("final_top_k", 10)
        self.min_score_threshold = RETRIEVAL_CONFIG.get("min_score_threshold", 0.6)

        # 初始化组件（基于配置）
        self.query_enhancers = self._init_query_enhancers()
        self.retrievers = self._init_retrievers()
        self.post_processors = self._init_post_processors()

    def _init_query_enhancers(self) -> List[Any]:
        """初始化问题增强处理器链，基于query_enhancer_config配置"""
        if not self.query_enhancer_config:
            # 默认使用全局配置的查询增强器
            enhancers = []
            config = QUERY_ENHANCEMENT_CONFIG
            if config.get("enable_context_processing", True):
                enhancers.append(component_registry.get_query_enhancer("context"))
            if config.get("enable_intent_recognition", True):
                enhancers.append(component_registry.get_query_enhancer("intent"))
            if config.get("enable_query_rewrite", True):
                enhancers.append(component_registry.get_query_enhancer("rewrite"))
            if config.get("enable_query_expansion", True):
                enhancers.append(component_registry.get_query_enhancer("expander"))
            return enhancers

        # 解析自定义配置
        pipeline = []
        for item in self.query_enhancer_config:
            if isinstance(item, str):
                # 仅指定名称，使用默认配置
                pipeline.append(component_registry.get_query_enhancer(item))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                # 指定名称和配置
                name, config = item
                pipeline.append(component_registry.get_query_enhancer(name, config))
            else:
                raise ValueError(f"无效的查询增强器配置: {item}")
        return pipeline

    def _init_retrievers(self) -> Dict[str, Any]:
        """初始化检索器实例，基于retriever_config配置"""
        if not self.retriever_config:
            # 默认初始化所有可用检索器
            return {
                "semantic": component_registry.get_retriever("vector"),
                "keyword": component_registry.get_retriever("keyword"),
                "hybrid": component_registry.get_retriever("hybrid"),
                "sql": component_registry.get_retriever("sql"),
                "api": component_registry.get_retriever("api")
            }

        # 解析自定义配置
        retrievers = {}
        for alias, config in self.retriever_config.items():
            if isinstance(config, str):
                # 仅指定组件名称
                retrievers[alias] = component_registry.get_retriever(config)
            elif isinstance(config, (list, tuple)) and len(config) == 2:
                # 指定名称和配置
                name, component_config = config
                retrievers[alias] = component_registry.get_retriever(name, component_config)
            else:
                raise ValueError(f"无效的检索器配置: {config}")
        return retrievers

    def _init_post_processors(self) -> List[Any]:
        """初始化后处理器链，基于post_processor_config配置"""
        if not self.post_processor_config:
            # 默认使用全局配置的后处理器
            processors = []
            config = POST_PROCESSING_CONFIG
            if config.get("enable_deduplication", True):
                processors.append(component_registry.get_post_processor("deduplicator"))
            if config.get("enable_filtering", True):
                processors.append(component_registry.get_post_processor("filter"))
            if config.get("enable_merging", True):
                processors.append(component_registry.get_post_processor("merger"))
            if config.get("enable_reranking", True):
                processors.append(component_registry.get_post_processor("reranker"))
            return processors

        # 解析自定义配置
        pipeline = []
        for item in self.post_processor_config:
            if isinstance(item, str):
                # 仅指定名称，使用默认配置
                pipeline.append(component_registry.get_post_processor(item))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                # 指定名称和配置
                name, config = item
                pipeline.append(component_registry.get_post_processor(name, config))
            else:
                raise ValueError(f"无效的后处理器配置: {item}")
        return pipeline

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
