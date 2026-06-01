"""工具系统实现"""
from typing import Any, Dict, List, Optional
from ..core.tool import BaseTool, BaseToolSystem

class ToolSystem(BaseToolSystem):
    """
    工具管理系统实现
    负责工具的注册、查询和执行
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        if not isinstance(tool, BaseTool):
            raise ValueError("工具必须继承自BaseTool抽象基类")
        if not tool.name:
            raise ValueError("工具名称不能为空")

        self._tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return self._tools.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否存在"""
        return tool_name in self._tools

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """执行工具调用"""
        tool = self.get_tool(tool_name)
        if not tool:
            return f"工具 {tool_name} 不存在"

        # 验证参数
        if not tool.validate_parameters(parameters):
            return f"工具 {tool_name} 参数验证失败，缺少必填参数"

        try:
            result = tool.execute(parameters)
            return str(result)
        except Exception as e:
            return f"工具 {tool_name} 执行失败: {str(e)}"

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取所有已注册工具的function definition列表"""
        return [tool.get_function_definition() for tool in self._tools.values()]

    def list_tools(self) -> List[str]:
        """获取所有已注册工具的名称列表"""
        return list(self._tools.keys())

    def unregister_tool(self, tool_name: str) -> bool:
        """注销工具"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def clear(self) -> None:
        """清空所有已注册工具"""
        self._tools.clear()
