"""
Agent模块 - 基于ReAct范式的多Agent系统实现
提供通用Agent基类和核心组件，支持业务Agent快速扩展
"""

# 导出核心接口
from .core.base_agent import BaseAgent
from .core.memory import BaseMemory, BaseShortTermMemory, BaseLongTermMemory
from .core.tool import BaseTool, BaseToolSystem
from .core.asset import BaseAssetStore
from .core.context import BaseContextBuilder

# 导出具体实现
from .implementations.react_agent import ReActAgent
from .implementations.search_agent import SearchAgent, search_agent
from .implementations.short_term_memory import ShortTermMemory
from .implementations.long_term_memory import LongTermMemory
from .implementations.tool_system import ToolSystem
from .implementations.local_asset_store import LocalAssetStore
from .implementations.prompt_builder import PromptBuilder

# 导出工具
from .utils.tool_registry import ToolRegistry, register_tool
from .utils.asset_serializer import AssetSerializer, SerializerType
from .utils.prompt_template import PromptTemplate

# 导出兼容层接口
from .compatibility import (
    SessionContext,
    SessionManager,
    session_manager,
    Agent,
    agent,
    Message,
    ChatResponse
)

__version__ = "1.0.0"
__all__ = [
    "BaseAgent",
    "BaseMemory",
    "BaseShortTermMemory",
    "BaseLongTermMemory",
    "BaseTool",
    "BaseToolSystem",
    "BaseAssetStore",
    "BaseContextBuilder",
    "ReActAgent",
    "SearchAgent",
    "search_agent",
    "ShortTermMemory",
    "LongTermMemory",
    "ToolSystem",
    "LocalAssetStore",
    "PromptBuilder",
    "ToolRegistry",
    "register_tool",
    "AssetSerializer",
    "SerializerType",
    "PromptTemplate",
    # 兼容层接口
    "SessionContext",
    "SessionManager",
    "session_manager",
    "Agent",
    "agent",
    "Message",
    "ChatResponse"
]
