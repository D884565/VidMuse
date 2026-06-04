# backend/tests/search/test_post_processors.py
import pytest
from backend.v1.app.search.core.models import SearchResult
from backend.v1.app.search.processors.post_processing.deduplicator import Deduplicator
from backend.v1.app.search.processors.post_processing.filter import ResultFilter
from backend.v1.app.search.processors.post_processing.merger import ResultMerger
from backend.v1.app.search.processors.post_processing.reranker import Reranker

@pytest.fixture
def test_results():
    return [
        SearchResult(result_id="1", content="重复内容", score=0.9, source="vector_db", source_type="faq", metadata={"product_id": "123"}),
        SearchResult(result_id="2", content="重复内容", score=0.85, source="mysql", source_type="product", metadata={"product_id": "123"}),
        SearchResult(result_id="3", content="唯一内容1", score=0.8, source="vector_db", source_type="document", metadata={"product_id": "123"}),
        SearchResult(result_id="4", content="唯一内容2", score=0.7, source="http_api", source_type="external", metadata={"product_id": "456"}),
        SearchResult(result_id="5", content="低相关内容", score=0.3, source="vector_db", source_type="faq", metadata={"product_id": "123"}),
    ]

def test_deduplicator(test_results):
    """测试去重处理器"""
    deduplicator = Deduplicator()
    processed = deduplicator.process(test_results)

    # 应该去掉一个重复内容
    assert len(processed) == 4
    # 保留得分更高的那个
    assert any(res.result_id == "1" for res in processed)
    assert not any(res.result_id == "2" for res in processed)

def test_result_filter(test_results):
    """测试过滤处理器"""
    filter_config = {
        "min_score": 0.5,
        "allowed_sources": ["vector_db", "mysql"],
        "filter_rules": {"product_id": "123"}
    }
    result_filter = ResultFilter(filter_config)
    processed = result_filter.process(test_results)

    # 应该过滤掉得分<0.5、来源不是vector_db/mysql、product_id不是123的结果
    assert len(processed) == 3
    assert all(res.score >= 0.5 for res in processed)
    assert all(res.source in ["vector_db", "mysql"] for res in processed)
    assert all(res.metadata.get("product_id") == "123" for res in processed)

def test_result_merger(test_results):
    """测试合并处理器"""
    merger = ResultMerger()
    processed = merger.process(test_results)

    # 合并相同内容的结果，保留所有来源信息
    assert len(processed) == 4  # 重复内容合并为1个
    merged = next(res for res in processed if res.content == "重复内容")
    assert "sources" in merged.metadata
    assert "vector_db" in merged.metadata["sources"]
    assert "mysql" in merged.metadata["sources"]

def test_reranker(test_results):
    """测试重排序处理器"""
    reranker = Reranker()
    processed = reranker.process(test_results)

    # 应该按得分降序排列
    scores = [res.score for res in processed]
    assert scores == sorted(scores, reverse=True)
