"""Prompt构建器实现"""
from typing import Any, Dict, List, Optional
from ..core.context import BaseContextBuilder
from ..core.base_agent import BaseAgent
from ..config import AGENT_CONFIG

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

        system_prompt = f"""你是{agent.name}，{agent.description}。

## 核心能力
你基于ReAct范式工作，可以通过思考-行动-观察的循环来解决复杂问题。

## 可用工具
{tools_str}

## 工作流程
1. 思考：分析用户问题，决定是否需要使用工具
2. 行动：如果需要工具，调用合适的工具获取信息
3. 观察：根据工具返回的结果，继续思考或生成回答
4. 回答：当拥有足够信息时，给出最终答案

## 响应规则
- 回答要简洁、准确、有帮助
- 如果无法回答，坦诚告知，不要编造信息
- 工具调用要严格按照参数要求
- 每次最多调用5个工具
- 思考过程要清晰，不要暴露内部实现细节
"""
        return system_prompt

    def build_user_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """构建用户提示词"""
        if not context:
            return query

        context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])

        return f"""用户问题：{query}

上下文信息：
{context_str}

请根据以上信息回答用户问题。"""

    def build_tool_prompt(self, tool_results: List[Dict[str, Any]]) -> str:
        """构建工具结果提示词"""
        if not tool_results:
            return ""

        result_strs = []
        for i, result in enumerate(tool_results, 1):
            result_str = f"""<|工具结果{i}|>
工具名称: {result['tool_name']}
调用参数: {result.get('parameters', {})}
返回结果:
{result['result']}
<|工具结果结束|>"""
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
