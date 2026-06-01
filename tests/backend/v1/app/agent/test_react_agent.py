import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch
from backend.v1.app.agent.implementations.react_agent import ReActAgent
from backend.v1.app.agent.core.tool import BaseTool

class MockSearchTool(BaseTool):
    """模拟搜索工具"""
    name = "search"
    description = "搜索信息"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    def execute(self, parameters: Dict[str, Any]) -> str:
        query = parameters["query"]
        if "Python" in query:
            return "Python是一种编程语言，创建于1991年。"
        return "未找到相关信息"

def test_agent_initialization():
    """测试Agent初始化"""
    agent = ReActAgent(
        agent_id="test_agent",
        name="测试助手",
        description="测试用AI助手"
    )

    assert agent.agent_id == "test_agent"
    assert agent.name == "测试助手"
    assert agent.description == "测试用AI助手"
    assert agent.memory is not None
    assert agent.tool_system is not None
    assert agent.asset_store is not None
    assert agent.context_builder is not None

@patch.object(ReActAgent, '_call_llm')
def test_agent_direct_response(mock_call_llm):
    """测试Agent直接返回回答（不需要工具）"""
    mock_call_llm.return_value = {
        "content": "Python是一种非常流行的编程语言。",
        "tool_calls": None
    }

    agent = ReActAgent(agent_id="test_agent", name="测试助手")
    result = agent.run("Python是什么？")

    assert result["success"] is True
    assert "Python是一种非常流行的编程语言" in result["answer"]
    assert result["iterations"] == 1

@patch.object(ReActAgent, '_call_llm')
def test_agent_with_tool_call(mock_call_llm):
    """测试Agent调用工具"""
    # 第一次调用：返回工具调用
    mock_call_llm.side_effect = [
        {
            "content": "我需要搜索一下Python的相关信息。",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "search",
                    "parameters": {"query": "Python 简介"}
                }
            ]
        },
        {
            "content": "根据搜索结果，Python是一种编程语言，创建于1991年。",
            "tool_calls": None
        }
    ]

    agent = ReActAgent(agent_id="test_agent", name="测试助手")
    agent.tool_system.register_tool(MockSearchTool())

    result = agent.run("Python是什么时候创建的？")

    assert result["success"] is True
    assert "1991年" in result["answer"]
    assert result["iterations"] == 2
    assert mock_call_llm.call_count == 2