# backend/tests/search/test_query_base.py
import pytest
from backend.v1.app.search.processors.query_enhancement.base import BaseQueryProcessor
from backend.v1.app.search.core.models import SearchQuery

class TestQueryProcessor(BaseQueryProcessor):
    processor_name = "test_query_processor"

    def process(self, query, context=None):
        query.query_text = f"processed: {query.query_text}"
        return query

    async def aprocess(self, query, context=None):
        query.query_text = f"async_processed: {query.query_text}"
        return query

def test_query_processor():
    """测试查询处理器基础功能"""
    processor = TestQueryProcessor()
    query = SearchQuery(query_text="test")

    processed = processor.process(query)
    assert processed.query_text == "processed: test"

@pytest.mark.asyncio
async def test_async_query_processor():
    """测试异步查询处理器"""
    processor = TestQueryProcessor()
    query = SearchQuery(query_text="test")

    processed = await processor.aprocess(query)
    assert processed.query_text == "async_processed: test"
