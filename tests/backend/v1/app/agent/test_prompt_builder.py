import pytest
from unittest.mock import Mock
from backend.v1.app.agent.implementations.prompt_builder import PromptBuilder

def test_build_system_prompt():
    """测试构建系统提示词"""
    builder = PromptBuilder()

    # 创建模拟Agent
    agent = Mock()
    agent.name = "测试助手"
    agent.description = "这是一个测试助手，擅长回答问题"

    # 模拟工具系统
    mock_tool = Mock()
    mock_tool.name = "search_tool"
    mock_tool.description = "搜索信息的工具"

    mock_tool_system = Mock()
    mock_tool_system.list_tools.return_value = ["search_tool"]
    mock_tool_system.get_tool.return_value = mock_tool
    agent.tool_system = mock_tool_system

    system_prompt = builder.build_system_prompt(agent)
    assert "测试助手" in system_prompt
    assert "这是一个测试助手" in system_prompt
    assert "ReAct" in system_prompt
    assert "工具调用" in system_prompt
    assert "search_tool" in system_prompt

def test_build_user_prompt():
    """测试构建用户提示词"""
    builder = PromptBuilder()

    prompt = builder.build_user_prompt("你好，请问Python是什么？", {"user_id": "123", "user_name": "测试用户"})
    assert "你好，请问Python是什么？" in prompt
    assert "user_id: 123" in prompt
    assert "user_name: 测试用户" in prompt

def test_build_tool_prompt():
    """测试构建工具结果提示词"""
    builder = PromptBuilder()

    tool_results = [
        {
            "tool_name": "search_tool",
            "parameters": {"query": "Python"},
            "result": "Python是一种编程语言，由Guido van Rossum创建。"
        },
        {
            "tool_name": "search_tool",
            "parameters": {"query": "Python特点"},
            "result": "Python的特点包括语法简洁、可读性强、生态丰富。"
        }
    ]

    prompt = builder.build_tool_prompt(tool_results)
    assert "search_tool" in prompt
    assert "Python是一种编程语言" in prompt
    assert "Python的特点包括语法简洁" in prompt

def test_build_chat_messages():
    """测试构建完整的聊天消息列表"""
    builder = PromptBuilder()

    # 创建模拟Agent
    agent = Mock()
    agent.name = "测试助手"
    agent.description = "测试助手"
    agent.tool_system = None
    agent.memory = None

    messages = builder.build_chat_messages(agent, "你好")
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "你好"
