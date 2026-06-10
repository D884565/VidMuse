# backend/tests/search/test_exceptions.py
import pytest
from backend.v1.app.search.core.exceptions import (
    SearchError, ChannelError, ChannelTimeoutError,
    ProcessorError, QueryValidationError
)

def test_search_error():
    """测试基础检索异常"""
    with pytest.raises(SearchError) as exc_info:
        raise SearchError("测试异常")
    assert str(exc_info.value) == "测试异常"

def test_channel_error():
    """测试渠道异常"""
    with pytest.raises(ChannelError) as exc_info:
        raise ChannelError("vector_db", "连接失败")
    assert exc_info.value.channel_name == "vector_db"
    assert "渠道[vector_db]错误: 连接失败" in str(exc_info.value)

def test_channel_timeout_error():
    """测试渠道超时异常"""
    with pytest.raises(ChannelTimeoutError) as exc_info:
        raise ChannelTimeoutError("mysql", "查询超时")
    assert exc_info.value.channel_name == "mysql"
    assert "渠道[mysql]错误: 查询超时" in str(exc_info.value)

def test_processor_error():
    """测试处理器异常"""
    with pytest.raises(ProcessorError) as exc_info:
        raise ProcessorError("query_rewriter", "重写失败")
    assert exc_info.value.processor_name == "query_rewriter"
    assert "处理器[query_rewriter]错误: 重写失败" in str(exc_info.value)

def test_query_validation_error():
    """测试查询验证异常"""
    with pytest.raises(QueryValidationError) as exc_info:
        raise QueryValidationError("查询文本不能为空")
    assert "查询文本不能为空" in str(exc_info.value)
