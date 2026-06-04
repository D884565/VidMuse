# backend/tests/search/test_component_registry.py
import pytest
from unittest.mock import Mock
from backend.v1.app.search.core.component_registry import ComponentRegistry
from backend.v1.app.search.core.interfaces import SearchChannel, QueryEnhancementProcessor

class TestChannel(SearchChannel):
    channel_name = "test_channel"
    channel_type = "test"

    def search(self, query, context=None): return []
    async def asearch(self, query, context=None): return []
    def health_check(self): return True

class TestProcessor(QueryEnhancementProcessor):
    processor_name = "test_processor"

    def process(self, query, context=None): return query
    async def aprocess(self, query, context=None): return query

def test_registry_initialization():
    """测试注册中心初始化"""
    config = {
        "ENABLED_CHANNELS": ["test_channel"],
        "ENABLED_QUERY_PROCESSORS": ["test_processor"],
        "ENABLED_POST_PROCESSORS": []
    }
    registry = ComponentRegistry(config)
    assert registry.config == config

def test_channel_registration():
    """测试渠道注册和获取"""
    registry = ComponentRegistry({})
    channel = TestChannel()

    registry.register_channel(channel)
    assert "test_channel" in registry.channels
    assert registry.get_channel("test_channel") == channel

    channels = registry.get_enabled_channels(["test_channel"])
    assert len(channels) == 1
    assert channels[0] == channel

def test_processor_registration():
    """测试处理器注册和获取"""
    registry = ComponentRegistry({"ENABLED_QUERY_PROCESSORS": ["test_processor"]})
    processor = TestProcessor()

    registry.register_query_processor(processor)
    assert "test_processor" in registry.query_processors

    processors = registry.get_query_processors()
    assert len(processors) == 1
    assert processors[0] == processor
