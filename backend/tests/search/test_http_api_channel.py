# backend/tests/search/test_http_api_channel.py
import pytest
from unittest.mock import Mock, patch
import aiohttp
from backend.v1.app.search.processors.retrieval.channels.http_api_channel import HttpApiChannel
from backend.v1.app.search.core.models import SearchQuery, SearchResult

@pytest.fixture
def http_api_channel():
    config = {
        "endpoint": "https://api.example.com/search",
        "api_key": "test_key",
        "timeout": 10,
        "weight": 0.7
    }
    return HttpApiChannel(config)

def test_channel_properties(http_api_channel):
    """测试渠道属性"""
    assert http_api_channel.channel_name == "http_api"
    assert http_api_channel.channel_type == "http_api"

@pytest.mark.asyncio
async def test_async_search(http_api_channel):
    """测试异步HTTP检索"""
    mock_response = {
        "results": [
            {"id": "api_1", "content": "API结果1", "score": 0.9, "type": "external"},
            {"id": "api_2", "content": "API结果2", "score": 0.8, "type": "external"}
        ]
    }

    with patch("aiohttp.ClientSession.post") as mock_post:
        async def mock_json():
            return mock_response

        mock_resp = Mock()
        mock_resp.status = 200
        mock_resp.json = mock_json
        mock_post.return_value.__aenter__.return_value = mock_resp

        query = SearchQuery(
            query_text="测试查询",
            top_k=2
        )

        results = await http_api_channel.asearch(query)

        assert len(results) == 2
        assert results[0].result_id == "api_1"
        assert results[0].content == "API结果1"
        assert results[0].score == 0.9 * 0.7
        assert results[0].source == "http_api"

        # 验证请求参数
        mock_post.assert_called_once_with(
            "https://api.example.com/search",
            json={
                "query": "测试查询",
                "limit": 2,
                "filters": {},
                "metadata": {}
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": "VidMuse-Search-Engine/1.0",
                "Authorization": "Bearer test_key"
            }
        )
