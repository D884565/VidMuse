# backend/tests/search/test_post_base.py
import pytest
from backend.v1.app.search.processors.post_processing.base import BasePostProcessor
from backend.v1.app.search.core.models import SearchResult

class TestPostProcessor(BasePostProcessor):
    processor_name = "test_post_processor"

    def process(self, results, context=None):
        for res in results:
            res.score = res.score * 0.5
        return results

    async def aprocess(self, results, context=None):
        for res in results:
            res.score = res.score * 0.5
        return results

def test_post_processor():
    """测试后处理器基础功能"""
    processor = TestPostProcessor()
    results = [
        SearchResult(result_id="1", content="test1", score=1.0, source="test", source_type="test"),
        SearchResult(result_id="2", content="test2", score=0.8, source="test", source_type="test")
    ]

    processed = processor.process(results)
    assert processed[0].score == 0.5
    assert processed[1].score == 0.4

@pytest.mark.asyncio
async def test_async_post_processor():
    """测试异步后处理器"""
    processor = TestPostProcessor()
    results = [
        SearchResult(result_id="1", content="test1", score=1.0, source="test", source_type="test"),
        SearchResult(result_id="2", content="test2", score=0.8, source="test", source_type="test")
    ]

    processed = await processor.aprocess(results)
    assert processed[0].score == 0.5
    assert processed[1].score == 0.4
