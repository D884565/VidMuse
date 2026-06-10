"""工具系统抽象基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseTool(ABC):
    """
    工具抽象基类，所有工具都必须继承此类
    子类需要设置name、description、parameters_schema类属性
    """
    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行工具逻辑
        :param parameters: 工具参数，已通过schema验证
        :return: 工具执行结果，字符串格式
        """
        pass

    def get_function_definition(self) -> Dict[str, Any]:
        """转换为大模型function calling所需的格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        验证参数是否符合schema定义
        简单实现，复杂场景可以使用jsonschema库
        """
        if "required" in self.parameters_schema:
            for required_param in self.parameters_schema["required"]:
                if required_param not in parameters:
                    return False
        return True

class BaseToolSystem(ABC):
    """工具管理系统抽象基类"""

    @abstractmethod
    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        pass

    @abstractmethod
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """执行工具调用"""
        pass

    @abstractmethod
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取所有已注册工具的function definition列表"""
        pass

    @abstractmethod
    def list_tools(self) -> List[str]:
        """获取所有已注册工具的名称列表"""
        pass
