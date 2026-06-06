"""Prompt构建器实现"""
from typing import Any, Dict, List, Optional
from ..core.context import BaseContextBuilder
from ..core.base_agent import BaseAgent
from ..config import AGENT_CONFIG
from backend.v1.app.pipeline.utils.prompt_manager import prompt_manager

class PromptBuilder(BaseContextBuilder):
    """
    默认的Prompt构建器实现
    支持模板渲染和动态上下文构建
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化Prompt构建器
        :param template_dir: 模板目录，默认使用配置中的值
        """
        self.template_dir = template_dir or AGENT_CONFIG["context"]["template_dir"]

    def build_system_prompt(self, agent: BaseAgent) -> str:
        """构建系统提示词"""
        tool_names = []
        tool_descriptions = []

        if agent.tool_system:
            tools = agent.tool_system.list_tools()
            tool_names = tools
            for tool_name in tools:
                tool = agent.tool_system.get_tool(tool_name)
                if tool:
                    tool_descriptions.append(f"- {tool.name}: {tool.description}")

        tools_str = "\n".join(tool_descriptions) if tool_descriptions else "无可用工具"

        # 使用统一的PromptManager加载系统提示词
        return prompt_manager.get_agent_default_system_prompt(
            agent_name=agent.name,
            agent_description=agent.description,
            tools_str=tools_str
        )

    def build_user_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """构建用户提示词"""
        if not context:
            return query

        context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])

        # 使用统一的PromptManager加载用户提示词
        return prompt_manager.get_agent_user_prompt(
            query=query,
            context_str=context_str
        )

    def build_tool_prompt(self, tool_results: List[Dict[str, Any]]) -> str:
        """构建工具结果提示词"""
        if not tool_results:
            return ""

        result_strs = []
        for i, result in enumerate(tool_results, 1):
            # 使用统一的PromptManager加载工具结果提示词
            result_str = prompt_manager.get_agent_tool_result_prompt(
                index=i,
                tool_name=result['tool_name'],
                parameters=str(result.get('parameters', {})),
                result=result['result']
            )
            result_strs.append(result_str)

        return "\n\n".join(result_strs) + "\n\n请根据以上工具返回结果继续处理用户问题。"

    def build_chat_messages(
        self,
        agent: BaseAgent,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        include_history: bool = True
    ) -> List[Dict[str, str]]:
        """构建完整的聊天消息列表"""
        messages = []

        # 添加系统提示词
        system_prompt = self.build_system_prompt(agent)
        messages.append({"role": "system", "content": system_prompt})

        # 添加历史消息
        if include_history and agent.memory:
            recent_memories = agent.memory.get_recent(20)
            for memory in recent_memories:
                content = memory["content"]
                if isinstance(content, dict):
                    if content.get("type") == "user_query":
                        messages.append({"role": "user", "content": content["content"]})
                    elif content.get("type") == "agent_response":
                        messages.append({"role": "assistant", "content": content["content"]})
                    elif content.get("type") == "tool_results":
                        tool_prompt = self.build_tool_prompt(content["content"])
                        messages.append({"role": "user", "content": tool_prompt})

        # 添加当前用户查询
        user_prompt = self.build_user_prompt(query, context)
        messages.append({"role": "user", "content": user_prompt})

        return messages
