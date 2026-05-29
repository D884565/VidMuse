from abc import ABC, abstractmethod
from typing import Dict, Any, List
import json


class BaseSearchTool(ABC):
    """检索工具抽象基类，所有检索工具必须继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称，必须唯一"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，说明工具的用途，用于大模型理解"""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """
        工具参数的JSON Schema定义
        参考：https://json-schema.org/learn/getting-started-step-by-step
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> str:
        """
        执行工具逻辑
        :param params: 工具参数，根据parameters_schema验证后的参数
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

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """
        验证参数是否符合schema定义
        简单实现，复杂场景可以使用jsonschema库
        """
        # 简单验证必填参数
        if "required" in self.parameters_schema:
            for required_param in self.parameters_schema["required"]:
                if required_param not in params:
                    return False
        return True
