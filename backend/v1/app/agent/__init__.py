"""
Agent模块 - 基于ReAct范式的多Agent系统实现
提供通用Agent基类和核心组件，支持业务Agent快速扩展
"""

# 导出核心接口
from .core.base_agent import BaseAgent
from .core.memory import BaseMemory, ShortTermMemory, LongTermMemory
from .core.tool import BaseTool, ToolSystem
from .core.asset import BaseAssetStore
from .core.context import BaseContextBuilder

# 导出具体实现
from .implementations.react_agent import ReActAgent
from .implementations.local_asset_store import LocalAssetStore
from .implementations.prompt_builder import PromptBuilder

__version__ = "1.0.0"
__all__ = [
    "BaseAgent",
    "BaseMemory",
    "ShortTermMemory",
    "LongTermMemory",
    "BaseTool",
    "ToolSystem",
    "BaseAssetStore",
    "BaseContextBuilder",
    "ReActAgent",
    "LocalAssetStore",
    "PromptBuilder"
]
