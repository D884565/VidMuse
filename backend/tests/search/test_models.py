# backend/tests/search/test_models.py
import pytest
from datetime import datetime
from backend.v1.app.search.core.models import SearchQuery, SearchResult

def test_search_query_creation():
    """测试SearchQuery对象创建"""
    query = SearchQuery(
        query_text="测试查询",
        top_k=5,
        filters={"product_id": "123"},
        metadata={"user_id": 456},
        timeout=10
    )

    assert query.query_text == "测试查询"
    assert query.top_k == 5
    assert query.filters == {"product_id": "123"}
    assert query.metadata == {"user_id": 456}
    assert query.timeout == 10
    assert query.query_embedding is None
    assert query.required_channels is None

def test_search_result_creation():
    """测试SearchResult对象创建"""
    result = SearchResult(
        result_id="test_123",
        content="测试内容",
        score=0.95,
        source="vector_db",
        source_type="faq",
        metadata={"product_id": "123"}
    )

    assert result.result_id == "test_123"
    assert result.content == "测试内容"
    assert result.score == 0.95
    assert result.source == "vector_db"
    assert result.source_type == "faq"
    assert result.metadata == {"product_id": "123"}
    assert isinstance(result.created_at, datetime)
