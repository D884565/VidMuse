"""工具注册工具"""
from typing import Dict, Type, List
from ..core.tool import BaseTool

class ToolRegistry:
    """全局工具注册表，用于注册和获取工具类"""
    _tools: Dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> None:
        """注册工具类"""
        if not issubclass(tool_class, BaseTool):
            raise ValueError("工具类必须继承自BaseTool")
        if not tool_class.name:
            raise ValueError("工具类必须设置name属性")

        cls._tools[tool_class.name] = tool_class

    @classmethod
    def get(cls, tool_name: str) -> Type[BaseTool]:
        """获取工具类"""
        return cls._tools.get(tool_name)

    @classmethod
    def list_all(cls) -> List[str]:
        """获取所有已注册工具名称"""
        return list(cls._tools.keys())

    @classmethod
    def create_instance(cls, tool_name: str, config: Dict = None) -> BaseTool:
        """创建工具实例"""
        tool_class = cls.get(tool_name)
        if not tool_class:
            raise ValueError(f"工具 {tool_name} 未注册")
        return tool_class(config or {})

# 注册装饰器
def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """工具类注册装饰器"""
    ToolRegistry.register(cls)
    return cls
