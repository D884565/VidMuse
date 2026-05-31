"""组件注册中心
提供可插拔组件的注册、发现和实例化机制，支持动态选择和配置查询增强器、检索器和后处理器。
"""
from typing import Dict, Type, List, Any, Optional
from abc import ABC
import importlib
import inspect
from pathlib import Path

from .interfaces import BaseQueryEnhancer, BaseRetriever, BasePostProcessor
from ..config import (
    QUERY_ENHANCEMENT_CONFIG,
    RETRIEVAL_CONFIG,
    POST_PROCESSING_CONFIG
)


class ComponentRegistry:
    """组件注册中心，管理所有可插拔组件"""

    # 组件类型注册
    _registry: Dict[str, Dict[str, Type[Any]]] = {
        "query_enhancer": {},
        "retriever": {},
        "post_processor": {}
    }

    @classmethod
    def register(cls, component_type: str, name: str, component_class: Type[Any]) -> None:
        """注册组件

        :param component_type: 组件类型：query_enhancer/retriever/post_processor
        :param name: 组件名称，唯一标识
        :param component_class: 组件类
        """
        if component_type not in cls._registry:
            raise ValueError(f"未知组件类型: {component_type}")

        if name in cls._registry[component_type]:
            # 允许覆盖注册
            pass

        cls._registry[component_type][name] = component_class

    @classmethod
    def get_component_class(cls, component_type: str, name: str) -> Optional[Type[Any]]:
        """获取组件类

        :param component_type: 组件类型
        :param name: 组件名称
        :return: 组件类，不存在返回None
        """
        if component_type not in cls._registry:
            return None
        return cls._registry[component_type].get(name)

    @classmethod
    def list_components(cls, component_type: str) -> List[str]:
        """列出指定类型的所有可用组件"""
        if component_type not in cls._registry:
            return []
        return list(cls._registry[component_type].keys())

    @classmethod
    def create_instance(cls, component_type: str, name: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """创建组件实例

        :param component_type: 组件类型
        :param name: 组件名称
        :param config: 组件配置参数（传递给构造函数）
        :return: 组件实例
        """
        component_class = cls.get_component_class(component_type, name)
        if not component_class:
            raise ValueError(f"{component_type}类型的组件{name}不存在")

        config = config or {}
        return component_class(**config)

    @classmethod
    def create_pipeline(cls, component_type: str, names: List[str], configs: Optional[List[Dict[str, Any]]] = None) -> List[Any]:
        """创建组件处理流水线

        :param component_type: 组件类型
        :param names: 组件名称列表，按处理顺序排列
        :param configs: 每个组件对应的配置列表，与names一一对应
        :return: 组件实例列表
        """
        configs = configs or [{} for _ in names]
        if len(names) != len(configs):
            raise ValueError("组件名称列表与配置列表长度不匹配")

        pipeline = []
        for name, config in zip(names, configs):
            pipeline.append(cls.create_instance(component_type, name, config))
        return pipeline

    # ==================== 快捷方法 ====================

    @classmethod
    def get_query_enhancer(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseQueryEnhancer:
        """获取查询增强器实例"""
        return cls.create_instance("query_enhancer", name, config)

    @classmethod
    def get_retriever(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseRetriever:
        """获取检索器实例"""
        return cls.create_instance("retriever", name, config)

    @classmethod
    def get_post_processor(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BasePostProcessor:
        """获取后处理器实例"""
        return cls.create_instance("post_processor", name, config)

    @classmethod
    def create_query_enhancer_pipeline(cls, names: List[str], configs: Optional[List[Dict[str, Any]]] = None) -> List[BaseQueryEnhancer]:
        """创建查询增强处理流水线"""
        return cls.create_pipeline("query_enhancer", names, configs)

    @classmethod
    def create_post_processor_pipeline(cls, names: List[str], configs: Optional[List[Dict[str, Any]]] = None) -> List[BasePostProcessor]:
        """创建后处理流水线"""
        return cls.create_pipeline("post_processor", names, configs)

    @classmethod
    def auto_discover(cls) -> None:
        """手动注册所有组件，避免自动发现的循环导入问题"""
        # 导入组件类
        from ..processors.query_enhancement.context_processor import ContextProcessor
        from ..processors.query_enhancement.intent_recognizer import IntentRecognizer
        from ..processors.query_enhancement.query_rewriter import QueryRewriter
        from ..processors.query_enhancement.query_expander import QueryExpander

        from ..processors.retrieval.vector_retriever import VectorRetriever
        from ..processors.retrieval.chromadb_retriever import ChromaDBRetriever
        from ..processors.retrieval.keyword_retriever import KeywordRetriever
        from ..processors.retrieval.hybrid_retriever import HybridRetriever
        from ..processors.retrieval.sql_retriever import SQLRetriever
        from ..processors.retrieval.api_retriever import APIRetriever

        from ..processors.post_processing.deduplicator import Deduplicator
        from ..processors.post_processing.filter import Filter
        from ..processors.post_processing.merger import Merger
        from ..processors.post_processing.reranker import Reranker

        # 注册查询增强器
        cls.register("query_enhancer", "context", ContextProcessor)
        cls.register("query_enhancer", "intent", IntentRecognizer)
        cls.register("query_enhancer", "rewrite", QueryRewriter)
        cls.register("query_enhancer", "expander", QueryExpander)

        # 注册检索器
        cls.register("retriever", "vector", VectorRetriever)
        cls.register("retriever", "chromadb", ChromaDBRetriever)
        cls.register("retriever", "keyword", KeywordRetriever)
        cls.register("retriever", "hybrid", HybridRetriever)
        cls.register("retriever", "sql", SQLRetriever)
        cls.register("retriever", "api", APIRetriever)

        # 注册后处理器
        cls.register("post_processor", "deduplicator", Deduplicator)
        cls.register("post_processor", "filter", Filter)
        cls.register("post_processor", "merger", Merger)
        cls.register("post_processor", "reranker", Reranker)

        print("所有组件已注册完成")

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """驼峰命名转蛇形命名"""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


# 全局注册中心实例
component_registry = ComponentRegistry()

# 注意：auto_discover() 需要在所有模块导入完成后调用
# 由上层显式调用，避免循环导入
