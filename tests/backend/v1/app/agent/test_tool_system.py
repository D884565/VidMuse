import pytest
from typing import Dict, Any
from backend.v1.app.agent.core.tool import BaseTool
from backend.v1.app.agent.implementations.tool_system import ToolSystem

class TestTool(BaseTool):
    """测试工具"""
    name = "test_tool"
    description = "测试工具描述"
    parameters_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数1"},
            "param2": {"type": "integer", "description": "参数2"}
        },
        "required": ["param1"]
    }

    def execute(self, parameters: Dict[str, Any]) -> str:
        return f"执行成功: param1={parameters['param1']}, param2={parameters.get('param2', 0)}"

def test_tool_registration_and_execution():
    """测试工具注册和执行"""
    tool_system = ToolSystem()
    test_tool = TestTool()

    # 注册工具
    tool_system.register_tool(test_tool)

    # 检查工具是否存在
    assert tool_system.has_tool("test_tool") is True
    assert tool_system.get_tool("test_tool") is not None

    # 执行工具
    result = tool_system.execute_tool("test_tool", {"param1": "test_value", "param2": 123})
    assert result == "执行成功: param1=test_value, param2=123"

    # 测试缺少必填参数
    result = tool_system.execute_tool("test_tool", {"param2": 123})
    assert "参数验证失败" in result

    # 测试未知工具
    result = tool_system.execute_tool("unknown_tool", {})
    assert "工具 unknown_tool 不存在" in result

def test_tool_definitions():
    """测试获取工具定义"""
    tool_system = ToolSystem()
    tool_system.register_tool(TestTool())

    definitions = tool_system.get_tool_definitions()
    assert len(definitions) == 1
    assert definitions[0]["function"]["name"] == "test_tool"
    assert definitions[0]["function"]["description"] == "测试工具描述"

def test_list_tools():
    """测试列出所有工具"""
    tool_system = ToolSystem()
    tool_system.register_tool(TestTool())

    tools = tool_system.list_tools()
    assert len(tools) == 1
    assert tools[0] == "test_tool"
