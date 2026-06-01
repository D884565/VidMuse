"""上下文构建抽象基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent

class BaseContextBuilder(ABC):
    """
    上下文构建器抽象基类
    负责构建Agent运行所需的Prompt上下文，包括系统提示词、用户提示词、工具结果等
    """

    @abstractmethod
    def build_system_prompt(self, agent: BaseAgent) -> str:
        """
        构建系统提示词
        :param agent: Agent实例
        :return: 系统提示词
        """
        pass

    @abstractmethod
    def build_user_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        构建用户提示词
        :param query: 用户查询内容
        :param context: 额外上下文信息
        :return: 格式化后的用户提示词
        """
        pass

    @abstractmethod
    def build_tool_prompt(self, tool_results: List[Dict[str, Any]]) -> str:
        """
        构建工具结果提示词
        :param tool_results: 工具执行结果列表
        :return: 格式化后的工具结果提示词
        """
        pass

    @abstractmethod
    def build_chat_messages(
        self,
        agent: BaseAgent,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        include_history: bool = True
    ) -> List[Dict[str, str]]:
        """
        构建完整的聊天消息列表，用于大模型调用
        :param agent: Agent实例
        :param query: 用户查询内容
        :param context: 额外上下文信息
        :param include_history: 是否包含历史消息
        :return: 消息列表，格式符合大模型API要求
        """
        pass
