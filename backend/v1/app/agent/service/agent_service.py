from typing import Optional, List, Dict, Any
from ..dto.request import CreateSessionRequest, ChatRequest
from ..dto.response import CreateSessionResponse, ChatResponse, SessionHistoryResponse, Message
from ..core import session_manager, agent
from ..core.context import SessionContext


class AgentService:
    """Agent服务类，单例模式，提供统一的服务接口"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """创建新会话"""
        session_id = session_manager.create_session(
            user_id=request.user_id,
            metadata=request.metadata
        )
        return CreateSessionResponse(session_id=session_id)

    def send_message(self, request: ChatRequest) -> ChatResponse:
        """发送消息进行聊天"""
        session = session_manager.get_session(request.session_id)
        if not session:
            return ChatResponse(
                session_id=request.session_id,
                answer="会话不存在或已过期，请创建新会话",
                is_tool_call=False
            )

        # 调用Agent处理消息
        response = agent.chat(
            session_context=session,
            user_message=request.message,
            tool_call_enabled=request.tool_call_enabled
        )

        return response

    def get_session_history(self, session_id: str) -> Optional[SessionHistoryResponse]:
        """获取会话历史"""
        session = session_manager.get_session(session_id)
        if not session:
            return None

        return SessionHistoryResponse(
            session_id=session_id,
            messages=session.get_messages(),
            created_at=session.created_at,
            updated_at=session.updated_at
        )

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return session_manager.delete_session(session_id)


# 全局服务实例
agent_service = AgentService()
