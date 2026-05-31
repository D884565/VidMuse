from typing import Optional, List, Dict, Any
from ..dto.response import ChatResponse, Message
from .. import session_manager, agent
from ..context import SessionContext


class AgentService:
    """Agent服务类，单例模式，提供统一的内部调用接口"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(self, user_id: Optional[str] = None, project_id: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        创建新会话
        :param user_id: 用户ID（可选）
        :param project_id: 项目ID（可选）
        :param metadata: 会话元数据（可选）
        :return: session_id 会话ID
        """
        session_id = session_manager.create_session(
            user_id=user_id,
            project_id=project_id,
            metadata=metadata
        )
        return session_id

    def chat(
        self,
        session_id: str,
        message: str,
        tool_call_enabled: bool = True
    ) -> ChatResponse:
        """
        发送消息进行聊天
        :param session_id: 会话ID
        :param message: 用户消息内容
        :param tool_call_enabled: 是否启用工具调用，默认启用
        :return: ChatResponse 回答结果
        """
        session = session_manager.get_session(session_id)
        if not session:
            return ChatResponse(
                session_id=session_id,
                answer="会话不存在或已过期，请创建新会话",
                is_tool_call=False
            )

        # 调用Agent处理消息
        response = agent.chat(
            session_context=session,
            user_message=message,
            tool_call_enabled=tool_call_enabled
        )

        return response

    def quick_chat(
        self,
        message: str,
        tool_call_enabled: bool = True,
        user_id: Optional[str] = None,
        project_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        快速聊天接口，无需手动管理会话，自动创建临时会话
        :param message: 用户消息
        :param tool_call_enabled: 是否启用工具调用
        :param user_id: 用户ID（可选）
        :param project_id: 项目ID（可选）
        :param metadata: 会话元数据（可选）
        :return: 回答内容字符串
        """
        # 创建临时会话
        session_id = self.create_session(user_id=user_id, project_id=project_id, metadata=metadata)
        response = self.chat(session_id, message, tool_call_enabled)
        # 用完即删
        self.delete_session(session_id)
        return response.answer

    def get_session_history(self, session_id: str) -> Optional[List[Message]]:
        """
        获取会话历史消息列表
        :param session_id: 会话ID
        :return: 消息列表，会话不存在返回None
        """
        session = session_manager.get_session(session_id)
        if not session:
            return None
        return session.get_messages()

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        :param session_id: 会话ID
        :return: 是否删除成功
        """
        return session_manager.delete_session(session_id)


# 全局服务实例
agent_service = AgentService()

