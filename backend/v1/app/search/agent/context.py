import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Lock

from backend.v1.app.search.agent.dto.response import Message
from backend.v1.app.search.agent_config import AGENT_CONFIG


class SessionContext:
    """会话上下文，管理单个会话的所有信息"""

    def __init__(self, session_id: str, user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_active_at = time.time()  # 最后活跃时间戳，用于超时判断
        self.messages: List[Message] = []  # 消息历史

    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self.messages.append(message)
        self.updated_at = datetime.now()
        self.last_active_at = time.time()

        # 限制历史消息数量，避免过长
        max_length = AGENT_CONFIG["session"]["max_history_length"]
        if len(self.messages) > max_length:
            # 保留系统提示和最新的消息
            self.messages = [self.messages[0]] + self.messages[-(max_length - 1):]

    def get_messages(self) -> List[Message]:
        """获取所有消息历史"""
        return self.messages.copy()

    def clear_history(self) -> None:
        """清空消息历史"""
        self.messages = []
        self.updated_at = datetime.now()

    def is_expired(self) -> bool:
        """判断会话是否过期"""
        timeout = AGENT_CONFIG["session"]["timeout"]
        return time.time() - self.last_active_at > timeout


class SessionManager:
    """会话管理器，单例模式"""
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: Dict[str, SessionContext] = {}
                    cls._instance._last_cleanup_time = time.time()
        return cls._instance

    def __init__(self):
        pass

    def create_session(self, user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建新会话，返回session_id"""
        # 先清理过期会话
        self._cleanup_expired_sessions()

        session_id = f"session_{uuid.uuid4().hex[:16]}"
        session = SessionContext(session_id, user_id, metadata)

        # 添加系统提示消息
        from .agent import system_prompt
        system_message = Message(
            role="system",
            content=system_prompt
        )
        session.add_message(system_message)

        self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话"""
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            session.last_active_at = time.time()
            return session
        return None

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _cleanup_expired_sessions(self) -> None:
        """清理过期会话"""
        now = time.time()
        cleanup_interval = AGENT_CONFIG["session"]["cleanup_interval"]

        # 按间隔清理，避免频繁清理
        if now - self._last_cleanup_time < cleanup_interval:
            return

        expired_ids = [
            session_id for session_id, session in self._sessions.items()
            if session.is_expired()
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        self._last_cleanup_time = now

    def get_all_sessions(self) -> Dict[str, SessionContext]:
        """获取所有会话（调试用）"""
        return self._sessions.copy()


# 全局会话管理器实例
session_manager = SessionManager()
