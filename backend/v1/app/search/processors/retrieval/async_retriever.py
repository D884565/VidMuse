# backend/v1/app/search/processors/retrieval/async_retriever.py
from typing import List, Optional, Dict, Any
import asyncio
import logging
from ...core.interfaces import SearchChannel
from ...core.models import SearchQuery, SearchResult
from ...core.component_registry import ComponentRegistry
from ...core.exceptions import ChannelTimeoutError

logger = logging.getLogger(__name__)

class AsyncRetriever:
    """异步检索执行器，并发调用多个检索渠道"""

    def __init__(self, registry: ComponentRegistry):
        """
        初始化异步检索执行器
        :param registry: 组件注册中心
        """
        self.registry = registry

    def search(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        同步检索（会阻塞，不推荐使用）
        :param query: 检索查询
        :param context: 上下文信息
        :return: 所有渠道的检索结果
        """
        import asyncio
        return asyncio.run(self.asearch(query, context))

    async def asearch(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        异步并发检索所有启用的渠道
        :param query: 检索查询
        :param context: 上下文信息
        :return: 所有渠道的检索结果合并列表
        """
        context = context or {}
        channels = self.registry.get_enabled_channels(query.required_channels)

        if not channels:
            logger.warning("没有启用的检索渠道")
            return []

        logger.info(f"开始并发检索 {len(channels)} 个渠道: {[ch.channel_name for ch in channels]}")

        # 创建所有渠道的检索任务
        tasks = []
        for channel in channels:
            task = self._search_channel(channel, query, context)
            tasks.append(task)

        # 并发执行所有任务，设置全局超时
        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.TimeoutError:
            logger.error(f"检索全局超时 ({query.timeout}s)")
            return []

        # 收集所有有效结果
        all_results = []
        for i, result in enumerate(results_list):
            channel = channels[i]
            if isinstance(result, Exception):
                logger.error(f"渠道[{channel.channel_name}]检索失败: {str(result)}", exc_info=result)
                continue

            if result:
                all_results.extend(result)
                logger.debug(f"渠道[{channel.channel_name}]返回 {len(result)} 条结果")

        logger.info(f"所有渠道检索完成，共获取 {len(all_results)} 条结果")
        return all_results

    async def _search_channel(self, channel: SearchChannel, query: SearchQuery, context: Dict[str, Any]) -> List[SearchResult]:
        """
        检索单个渠道，带超时控制
        :param channel: 检索渠道
        :param query: 检索查询
        :param context: 上下文信息
        :return: 渠道返回的结果
        """
        try:
            # 单个渠道的超时时间取全局超时和渠道配置的较小值
            timeout = min(
                query.timeout,
                self.registry.config.get("CHANNEL_CONFIG", {}).get(channel.channel_name, {}).get("timeout", query.timeout)
            )

            return await asyncio.wait_for(
                channel.asearch(query, context),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"渠道[{channel.channel_name}]检索超时 ({timeout}s)")
            raise ChannelTimeoutError(channel.channel_name, f"检索超时 ({timeout}s)") from None
        except Exception as e:
            logger.error(f"渠道[{channel.channel_name}]检索异常: {str(e)}", exc_info=True)
            raise
