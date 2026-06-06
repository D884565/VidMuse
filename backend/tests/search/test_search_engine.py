# backend/tests/search/test_search_engine.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from backend.v1.app.search import SearchEngine
from backend.v1.app.search.core.models import SearchQuery, SearchResult

@pytest.fixture
def search_engine():
    """创建SearchEngine实例，使用测试配置"""
    test_config = {
        "ENABLED_CHANNELS": [],
        "ENABLED_QUERY_PROCESSORS": [],
        "ENABLED_POST_PROCESSORS": []
    }
    return SearchEngine(test_config)

def test_search_engine_initialization(search_engine):
    """测试搜索引擎初始化"""
    assert search_engine is not None
    assert search_engine.registry is not None
    assert search_engine.retriever is not None

def test_add_channel(search_engine):
    """测试动态添加渠道"""
    mock_channel = Mock()
    mock_channel.channel_name = "test_channel"
    mock_channel.channel_type = "test"

    search_engine.add_channel(mock_channel)

    assert "test_channel" in search_engine.registry.channels
    assert search_engine.registry.get_channel("test_channel") == mock_channel

def test_add_processor(search_engine):
    """测试动态添加处理器"""
    mock_processor = Mock()
    mock_processor.processor_name = "test_processor"

    search_engine.add_query_processor(mock_processor)
    assert "test_processor" in search_engine.registry.query_processors

    search_engine.add_post_processor(mock_processor)
    assert "test_processor" in search_engine.registry.post_processors

@pytest.mark.asyncio
async def test_full_search_flow():
    """测试完整的检索流程"""
    # 模拟渠道返回结果
    mock_result = SearchResult(
        result_id="1",
        content="测试结果",
        score=0.9,
        source="test_channel",
        source_type="test"
    )

    mock_channel = Mock()
    mock_channel.channel_name = "test_channel"
    # 异步方法
    async def mock_asearch(query, context=None):
        return [mock_result]
    mock_channel.asearch = mock_asearch
    mock_channel.health_check = Mock(return_value=True)

    # 模拟处理器（异步方法）
    mock_query_processor = Mock()
    mock_query_processor.processor_name = "test_query_processor"
    async def mock_query_process(q, c=None):
        return q
    mock_query_processor.aprocess = mock_query_process

    mock_post_processor = Mock()
    mock_post_processor.processor_name = "test_post_processor"
    async def mock_post_process(r, c=None):
        return r
    mock_post_processor.aprocess = mock_post_process

    # 创建搜索引擎
    config = {
        "ENABLED_CHANNELS": ["test_channel"],
        "ENABLED_QUERY_PROCESSORS": ["test_query_processor"],
        "ENABLED_POST_PROCESSORS": ["test_post_processor"]
    }
    engine = SearchEngine(config)
    engine.add_channel(mock_channel)
    engine.add_query_processor(mock_query_processor)
    engine.add_post_processor(mock_post_processor)

    # 执行检索
    query = SearchQuery(query_text="测试查询")
    results = await engine.asearch(query)

    # 验证流程
    assert len(results) == 1
    assert results[0].content == "测试结果"
