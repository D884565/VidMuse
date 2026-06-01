"""兼容层，适配原有search.agent的接口"""
from typing import Optional, Dict, Any, List
from .implementations.search_agent import SearchAgent
from .implementations.short_term_memory import ShortTermMemory
from .implementations.prompt_builder import PromptBuilder

# 兼容原有SessionContext
class SessionContext(ShortTermMemory):
    """
    兼容原有SessionContext接口
    继承自ShortTermMemory，添加原有接口方法
    """

    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        project_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.session_id = session_id
        self.user_id = user_id
        self.project_id = project_id
        self.metadata = metadata or {}

        # 兼容原有属性
        from datetime import datetime
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_active_at = datetime.now().timestamp()

    def add_message(self, message: Dict[str, Any]) -> None:
        """兼容原有add_message接口"""
        self.add(message)
        from datetime import datetime
        self.updated_at = datetime.now()
        self.last_active_at = datetime.now().timestamp()

    def get_messages(self) -> List[Dict[str, Any]]:
        """兼容原有get_messages接口"""
        return [mem["content"] for mem in self.get_recent()]

    def clear_history(self) -> None:
        """兼容原有clear_history接口"""
        self.clear()
        from datetime import datetime
        self.updated_at = datetime.now()

    def is_expired(self, timeout: int = 3600) -> bool:
        """兼容原有is_expired接口"""
        import time
        return time.time() - self.last_active_at > timeout


# 兼容原有SessionManager
class SessionManager:
    """
    兼容原有SessionManager接口
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._sessions = {}
        return cls._instance

    def create_session(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建新会话"""
        import uuid
        session_id = f"session_{uuid.uuid4().hex[:16]}"
        session = SessionContext(session_id, user_id, project_id, metadata)
        self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话"""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# 全局实例
session_manager = SessionManager()

# 兼容原有Agent接口
class Agent(SearchAgent):
    """
    兼容原有Agent类接口
    """

    def __init__(self):
        super().__init__(
            agent_id="default_search_agent",
            name="搜索助手",
            description="智能搜索助手"
        )

    def chat(
        self,
        session_context: SessionContext,
        user_message: str,
        tool_call_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        兼容原有chat接口
        :param session_context: 会话上下文
        :param user_message: 用户消息
        :param tool_call_enabled: 是否启用工具调用
        :return: 回答结果
        """
        # 构建上下文
        context = {
            "session_id": session_context.session_id,
            "user_id": session_context.user_id,
            "project_id": session_context.project_id,
            "metadata": session_context.metadata
        }

        # 调用父类方法
        result = super().chat(
            user_message,
            context=context
        )

        # 适配原有返回格式
        return {
            "session_id": session_context.session_id,
            "answer": result["answer"],
            "is_tool_call": len(result.get("tool_calls", [])) > 0,
            "tool_name": result["tool_calls"][0]["name"] if result.get("tool_calls") else None,
            "tool_params": result["tool_calls"][0]["parameters"] if result.get("tool_calls") else None,
            "tool_result": result["tool_results"][0] if result.get("tool_results") else None,
            "metadata": {
                "iterations": result["iterations"],
                "time_cost": result["time_cost"],
                "success": result["success"]
            }
        }


# 兼容原有全局agent实例
try:
    agent = Agent()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"初始化兼容Agent失败: {str(e)}")
    agent = None

# 兼容原有Message类
class Message:
    """兼容原有Message类"""
    def __init__(self, role: str, content: str, **kwargs):
        self.role = role
        self.content = content
        self.extra = kwargs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            **self.extra
        }


# 兼容原有ChatResponse类
class ChatResponse:
    """兼容原有ChatResponse类"""
    def __init__(
        self,
        session_id: str,
        answer: str,
        is_tool_call: bool = False,
        tool_name: Optional[str] = None,
        tool_params: Optional[Dict[str, Any]] = None,
        tool_result: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.session_id = session_id
        self.answer = answer
        self.is_tool_call = is_tool_call
        self.tool_name = tool_name
        self.tool_params = tool_params
        self.tool_result = tool_result
        self.metadata = metadata or {}


# 导出兼容接口
__all__ = [
    "SessionContext",
    "SessionManager",
    "session_manager",
    "Agent",
    "agent",
    "Message",
    "ChatResponse"
]
