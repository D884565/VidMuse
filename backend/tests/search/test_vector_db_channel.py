# backend/tests/search/test_vector_db_channel.py
import pytest
from unittest.mock import Mock, patch
from backend.v1.app.search.processors.retrieval.channels.vector_db_channel import VectorDBChannel
from backend.v1.app.search.core.models import SearchQuery, SearchResult

@pytest.fixture
def mock_vector_client():
    mock_client = Mock()
    mock_client.query_similar.return_value = {
        "ids": [["id1", "id2"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [[{"product_id": "123", "type": "faq"}, {"product_id": "123", "type": "document"}]],
        "documents": [["如何重置密码？", "产品使用说明书"]]
    }
    return mock_client

@pytest.fixture
def vector_db_channel(mock_vector_client):
    config = {"collection": "test_collection", "weight": 1.0}
    with patch("backend.v1.app.search.processors.retrieval.channels.vector_db_channel.get_vector_db_client",
               return_value=mock_vector_client):
        channel = VectorDBChannel(config)
        return channel

def test_channel_properties(vector_db_channel):
    """测试渠道属性"""
    assert vector_db_channel.channel_name == "vector_db"
    assert vector_db_channel.channel_type == "vector_db"
    assert vector_db_channel.health_check() is True

def test_sync_search(vector_db_channel, mock_vector_client):
    """测试同步检索"""
    query = SearchQuery(
        query_text="测试查询",
        top_k=2,
        filters={"product_id": "123"}
    )
    query.query_embedding = [0.1, 0.2, 0.3]

    results = vector_db_channel.search(query)

    assert len(results) == 2
    assert isinstance(results[0], SearchResult)
    assert results[0].result_id == "id1"
    assert results[0].content == "如何重置密码？"
    assert results[0].score == 0.9  # 1 - 0.1
    assert results[0].source == "vector_db"
    assert results[0].source_type == "faq"

    mock_vector_client.query_similar.assert_called_once_with(
        query_embeddings=[[0.1, 0.2, 0.3]],
        n_results=2,
        where={"product_id": "123"}
    )

@pytest.mark.asyncio
async def test_async_search(vector_db_channel, mock_vector_client):
    """测试异步检索"""
    query = SearchQuery(
        query_text="测试查询",
        top_k=2
    )
    query.query_embedding = [0.1, 0.2, 0.3]

    results = await vector_db_channel.asearch(query)

    assert len(results) == 2
    mock_vector_client.query_similar.assert_called_once()
