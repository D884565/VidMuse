# backend/tests/search/test_async_retriever.py
import pytest
import asyncio
from unittest.mock import Mock
from backend.v1.app.search.processors.retrieval.async_retriever import AsyncRetriever
from backend.v1.app.search.core.component_registry import ComponentRegistry
from backend.v1.app.search.core.models import SearchQuery, SearchResult

class MockChannel1:
    channel_name = "channel1"
    channel_type = "test"

    async def asearch(self, query, context=None):
        await asyncio.sleep(0.1)
        return [
            SearchResult(result_id="1", content="结果1", score=0.9, source="channel1", source_type="test")
        ]

    def search(self, query, context=None):
        return []

    def health_check(self): return True

class MockChannel2:
    channel_name = "channel2"
    channel_type = "test"

    async def asearch(self, query, context=None):
        await asyncio.sleep(0.15)
        return [
            SearchResult(result_id="2", content="结果2", score=0.8, source="channel2", source_type="test")
        ]

    def search(self, query, context=None):
        return []

    def health_check(self): return True

class SlowChannel:
    channel_name = "slow_channel"
    channel_type = "test"

    async def asearch(self, query, context=None):
        await asyncio.sleep(2)  # 很慢的渠道
        return [
            SearchResult(result_id="3", content="慢结果", score=0.7, source="slow_channel", source_type="test")
        ]

    def search(self, query, context=None):
        return []

    def health_check(self): return True

@pytest.fixture
def async_retriever():
    registry = ComponentRegistry({"ENABLED_CHANNELS": ["channel1", "channel2"]})
    registry.register_channel(MockChannel1())
    registry.register_channel(MockChannel2())
    return AsyncRetriever(registry)

@pytest.mark.asyncio
async def test_concurrent_search(async_retriever):
    """测试并发检索多个渠道"""
    query = SearchQuery(query_text="test", timeout=1)

    results = await async_retriever.asearch(query)

    # 应该返回两个渠道的结果
    assert len(results) == 2
    assert any(res.source == "channel1" for res in results)
    assert any(res.source == "channel2" for res in results)

@pytest.mark.asyncio
async def test_channel_timeout():
    """测试渠道超时处理"""
    registry = ComponentRegistry({"ENABLED_CHANNELS": ["channel1", "slow_channel"]})
    registry.register_channel(MockChannel1())
    registry.register_channel(SlowChannel())
    retriever = AsyncRetriever(registry)

    query = SearchQuery(query_text="test", timeout=0.5)  # 超时时间0.5秒，小于慢渠道的2秒

    results = await retriever.asearch(query)

    # 应该只返回快渠道的结果，慢渠道超时被丢弃
    assert len(results) == 1
    assert results[0].source == "channel1"
