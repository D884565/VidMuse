# backend/tests/search/test_interfaces.py
import pytest
from abc import ABC
from backend.v1.app.search.core.interfaces import SearchChannel, BaseProcessor
from backend.v1.app.search.core.models import SearchQuery, SearchResult

def test_search_channel_is_abstract():
    """测试SearchChannel是抽象基类"""
    with pytest.raises(TypeError):
        SearchChannel()

def test_base_processor_is_abstract():
    """测试BaseProcessor是抽象基类"""
    with pytest.raises(TypeError):
        BaseProcessor()
