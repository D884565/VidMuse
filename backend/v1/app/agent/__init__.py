# Agentic RAG 模块
__version__ = "1.0.0"

# 核心类和实例导出，方便外部直接调用
from .core import agent, session_manager
from .service import agent_service
from .dto.response import ChatResponse, Message
from .tools.base import BaseTool

__all__ = [
    "agent_service",  # 推荐使用：直接导入全局服务实例
    "agent",
    "session_manager",
    "ChatResponse",
    "Message",
    "BaseTool",
]

