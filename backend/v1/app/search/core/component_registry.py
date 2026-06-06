# backend/v1/app/search/core/component_registry.py
from typing import Dict, List, Optional, Any
import logging
from .interfaces import SearchChannel, QueryEnhancementProcessor, PostProcessingProcessor
from .exceptions import SearchError

logger = logging.getLogger(__name__)

class ComponentRegistry:
    """组件注册中心，统一管理所有检索渠道和处理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化注册中心
        :param config: 配置信息
        """
        self.config = config or {}
        self.channels: Dict[str, SearchChannel] = {}
        self.query_processors: Dict[str, QueryEnhancementProcessor] = {}
        self.post_processors: Dict[str, PostProcessingProcessor] = {}

        # 自动注册内置组件
        self._register_builtin_components()

    def _register_builtin_components(self) -> None:
        """注册内置组件"""
        # 后续会自动发现并注册内置的渠道和处理器
        pass

    def register_channel(self, channel: SearchChannel) -> None:
        """
        注册检索渠道
        :param channel: 检索渠道实例
        """
        if channel.channel_name in self.channels:
            logger.warning(f"渠道[{channel.channel_name}]已存在，将被覆盖")
        self.channels[channel.channel_name] = channel
        logger.info(f"注册检索渠道: {channel.channel_name} ({channel.channel_type})")

    def register_query_processor(self, processor: QueryEnhancementProcessor) -> None:
        """
        注册查询增强处理器
        :param processor: 处理器实例
        """
        if processor.processor_name in self.query_processors:
            logger.warning(f"查询处理器[{processor.processor_name}]已存在，将被覆盖")
        self.query_processors[processor.processor_name] = processor
        logger.info(f"注册查询处理器: {processor.processor_name}")

    def register_post_processor(self, processor: PostProcessingProcessor) -> None:
        """
        注册结果后处理器
        :param processor: 处理器实例
        """
        if processor.processor_name in self.post_processors:
            logger.warning(f"后处理器[{processor.processor_name}]已存在，将被覆盖")
        self.post_processors[processor.processor_name] = processor
        logger.info(f"注册后处理器: {processor.processor_name}")

    def get_channel(self, channel_name: str) -> Optional[SearchChannel]:
        """
        获取指定名称的检索渠道
        :param channel_name: 渠道名称
        :return: 渠道实例，不存在返回None
        """
        return self.channels.get(channel_name)

    def get_enabled_channels(self, required_channels: Optional[List[str]] = None) -> List[SearchChannel]:
        """
        获取启用的检索渠道列表
        :param required_channels: 强制指定要使用的渠道，None表示使用配置中启用的渠道
        :return: 渠道实例列表
        """
        if required_channels:
            channels = []
            for name in required_channels:
                channel = self.get_channel(name)
                if channel:
                    channels.append(channel)
                else:
                    logger.warning(f"请求的渠道[{name}]不存在或未注册")
            return channels

        # 使用配置中启用的渠道
        enabled_names = self.config.get("ENABLED_CHANNELS", [])
        return [self.channels[name] for name in enabled_names if name in self.channels]

    def get_query_processors(self) -> List[QueryEnhancementProcessor]:
        """获取配置启用的查询增强处理器列表（按配置顺序）"""
        enabled_names = self.config.get("ENABLED_QUERY_PROCESSORS", [])
        return [self.query_processors[name] for name in enabled_names if name in self.query_processors]

    def get_post_processors(self) -> List[PostProcessingProcessor]:
        """获取配置启用的结果后处理器列表（按配置顺序）"""
        enabled_names = self.config.get("ENABLED_POST_PROCESSORS", [])
        return [self.post_processors[name] for name in enabled_names if name in self.post_processors]
