import pytest
from unittest.mock import Mock, patch
from backend.v1.app.agent.implementations.search_agent import SearchAgent
from backend.v1.app.search import SearchQuery

def test_search_agent_integration():
    """测试SearchAgent与检索模块的集成"""
    # 模拟检索引擎返回结果
    mock_results = [
        {"result_id": "1", "content": "测试结果1", "score": 0.9, "source": "vector_db"},
        {"result_id": "2", "content": "测试结果2", "score": 0.8, "source": "mysql"}
    ]

    with patch.object(SearchAgent, '_search_tool', return_value=mock_results):
        agent = SearchAgent()

        # 调用chat接口
        response = agent.chat(
            query="测试查询",
            user_id=123,
            project_id=456
        )

        # 验证返回结果
        assert response is not None
        # 实际返回格式根据Agent的实现而定，这里只验证工具被调用
        assert agent._search_tool.called
