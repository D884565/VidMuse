# backend/v1/app/search/search_engine.py
from typing import List, Dict, Any, Optional
import logging
from .core.models import SearchQuery, SearchResult
from .core.component_registry import ComponentRegistry
from .processors.retrieval.async_retriever import AsyncRetriever
from .processors.query_enhancement.query_rewriter import QueryRewriter
from .processors.query_enhancement.intent_recognizer import IntentRecognizer
from .processors.query_enhancement.context_processor import ContextProcessor
from .processors.post_processing.deduplicator import Deduplicator
from .processors.post_processing.filter import ResultFilter
from .processors.post_processing.merger import ResultMerger
from .processors.post_processing.reranker import Reranker
from .processors.retrieval.channels.vector_db_channel import VectorDBChannel
from .processors.retrieval.channels.mysql_channel import MySQLChannel
from .processors.retrieval.channels.http_api_channel import HttpApiChannel
from .config import SearchConfig

logger = logging.getLogger(__name__)

class SearchEngine:
    """多通道检索引擎对外统一入口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化检索引擎
        :param config: 自定义配置，会覆盖默认配置
        """
        # 加载配置
        if isinstance(config, dict):
            self.config = SearchConfig.from_dict(config)
        elif isinstance(config, SearchConfig):
            self.config = config
        else:
            self.config = SearchConfig()

        # 初始化组件注册中心
        self.registry = ComponentRegistry(self.config.to_dict())

        # 注册内置组件
        self._register_builtin_components()

        # 初始化检索执行器
        self.retriever = AsyncRetriever(self.registry)

        logger.info("多通道检索引擎初始化完成")
        logger.info(f"启用的渠道: {self.config.ENABLED_CHANNELS}")
        logger.info(f"启用的查询处理器: {self.config.ENABLED_QUERY_PROCESSORS}")
        logger.info(f"启用的后处理器: {self.config.ENABLED_POST_PROCESSORS}")

    def _register_builtin_components(self) -> None:
        """注册内置的所有组件"""
        # 注册检索渠道
        self._register_builtin_channels()

        # 注册查询处理器
        self._register_builtin_query_processors()

        # 注册后处理器
        self._register_builtin_post_processors()

    def _register_builtin_channels(self) -> None:
        """注册内置检索渠道"""
        channel_configs = self.config.CHANNEL_CONFIG

        # 向量数据库渠道
        if "vector_db" in channel_configs and channel_configs["vector_db"].get("enabled", True):
            try:
                vector_channel = VectorDBChannel(channel_configs["vector_db"])
                self.registry.register_channel(vector_channel)
            except Exception as e:
                logger.warning(f"注册向量数据库渠道失败: {str(e)}")

        # MySQL渠道
        if "mysql" in channel_configs and channel_configs["mysql"].get("enabled", True):
            try:
                mysql_channel = MySQLChannel(channel_configs["mysql"])
                self.registry.register_channel(mysql_channel)
            except Exception as e:
                logger.warning(f"注册MySQL渠道失败: {str(e)}")

        # HTTP API渠道
        if "http_api" in channel_configs and channel_configs["http_api"].get("enabled", False):
            try:
                http_channel = HttpApiChannel(channel_configs["http_api"])
                self.registry.register_channel(http_channel)
            except Exception as e:
                logger.warning(f"注册HTTP API渠道失败: {str(e)}")

    def _register_builtin_query_processors(self) -> None:
        """注册内置查询增强处理器"""
        processor_configs = self.config.POST_PROCESSOR_CONFIG

        # 上下文处理器
        try:
            self.registry.register_query_processor(ContextProcessor())
        except Exception as e:
            logger.warning(f"注册上下文处理器失败: {str(e)}")

        # 查询重写器
        try:
            self.registry.register_query_processor(QueryRewriter())
        except Exception as e:
            logger.warning(f"注册查询重写器失败: {str(e)}")

        # 意图识别器
        try:
            self.registry.register_query_processor(IntentRecognizer())
        except Exception as e:
            logger.warning(f"注册意图识别器失败: {str(e)}")

    def _register_builtin_post_processors(self) -> None:
        """注册内置结果后处理器"""
        processor_configs = self.config.POST_PROCESSOR_CONFIG

        # 结果过滤器
        try:
            filter_config = processor_configs.get("result_filter", {})
            self.registry.register_post_processor(ResultFilter(filter_config))
        except Exception as e:
            logger.warning(f"注册结果过滤器失败: {str(e)}")

        # 去重器
        try:
            dedup_config = processor_configs.get("deduplicator", {})
            self.registry.register_post_processor(Deduplicator(dedup_config))
        except Exception as e:
            logger.warning(f"注册去重器失败: {str(e)}")

        # 结果合并器
        try:
            merger_config = processor_configs.get("result_merger", {})
            self.registry.register_post_processor(ResultMerger(merger_config))
        except Exception as e:
            logger.warning(f"注册结果合并器失败: {str(e)}")

        # 重排序器
        try:
            rerank_config = processor_configs.get("reranker", {})
            self.registry.register_post_processor(Reranker(rerank_config))
        except Exception as e:
            logger.warning(f"注册重排序器失败: {str(e)}")

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        同步检索接口（不推荐，建议使用异步接口）
        :param query: 检索查询对象
        :return: 检索结果列表
        """
        import asyncio
        return asyncio.run(self.asearch(query))

    async def asearch(self, query: SearchQuery) -> List[SearchResult]:
        """
        异步检索接口（推荐）
        :param query: 检索查询对象
        :return: 检索结果列表
        """
        logger.info(f"开始检索: '{query.query_text}'")

        # 1. 查询增强处理
        processed_query = query
        for processor in self.registry.get_query_processors():
            try:
                processed_query = await processor.aprocess(processed_query)
            except Exception as e:
                if self.config.FAIL_FAST:
                    raise
                logger.error(f"查询处理器[{processor.processor_name}]执行失败，跳过: {str(e)}")

        # 2. 执行检索
        try:
            results = await self.retriever.asearch(processed_query)
        except Exception as e:
            logger.error(f"检索执行失败: {str(e)}", exc_info=True)
            if self.config.FAIL_FAST:
                raise
            return []

        # 3. 结果后处理
        processed_results = results
        for processor in self.registry.get_post_processors():
            try:
                processed_results = await processor.aprocess(processed_results)
            except Exception as e:
                if self.config.FAIL_FAST:
                    raise
                logger.error(f"后处理器[{processor.processor_name}]执行失败，跳过: {str(e)}")

        logger.info(f"检索完成，共返回 {len(processed_results)} 条结果")
        return processed_results

    def add_channel(self, channel: "SearchChannel") -> None:
        """
        动态添加检索渠道
        :param channel: 检索渠道实例
        """
        self.registry.register_channel(channel)

    def add_query_processor(self, processor: "QueryEnhancementProcessor") -> None:
        """
        动态添加查询增强处理器
        :param processor: 查询处理器实例
        """
        self.registry.register_query_processor(processor)

    def add_post_processor(self, processor: "PostProcessingProcessor") -> None:
        """
        动态添加结果后处理器
        :param processor: 后处理器实例
        """
        self.registry.register_post_processor(processor)

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查，检查所有渠道的健康状态
        :return: 健康检查结果
        """
        channels = self.registry.get_enabled_channels()
        health_status = {
            "status": "healthy",
            "channels": {},
            "total_channels": len(channels),
            "healthy_channels": 0
        }

        for channel in channels:
            try:
                is_healthy = channel.health_check()
                health_status["channels"][channel.channel_name] = "healthy" if is_healthy else "unhealthy"
                if is_healthy:
                    health_status["healthy_channels"] += 1
            except Exception as e:
                health_status["channels"][channel.channel_name] = f"error: {str(e)}"

        if health_status["healthy_channels"] == 0:
            health_status["status"] = "unhealthy"
        elif health_status["healthy_channels"] < len(channels):
            health_status["status"] = "degraded"

        return health_status
