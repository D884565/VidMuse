import json
import os
from typing import List, Dict, Any, Optional, Tuple
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv
from .dto.response import Message, ChatResponse
from ..tools.base import BaseSearchTool
from ..tools import ALL_TOOLS
from .context import SessionContext
from ..agent_config import AGENT_CONFIG

load_dotenv()

# 系统提示词
system_prompt = AGENT_CONFIG["system_prompt"]


class Agent:
    """Agent核心类，负责处理对话、工具调用和回答生成"""

    def __init__(self):
        # 初始化大模型客户端
        self.api_key = os.getenv("DOUBAO_SEED_API_KEY")
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.model = AGENT_CONFIG["model"]["name"]
        self.temperature = AGENT_CONFIG["model"]["temperature"]
        self.max_tokens = AGENT_CONFIG["model"]["max_tokens"]
        self.top_p = AGENT_CONFIG["model"]["top_p"]

        self.client = Ark(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # 加载工具
        self.tools: Dict[str, BaseTool] = self._load_tools()
        self.tool_definitions = [tool.get_function_definition() for tool in self.tools.values()]

    def _load_tools(self) -> Dict[str, BaseSearchTool]:
        """加载配置中启用的工具"""
        tools = {}
        enabled_tools = AGENT_CONFIG["tools"]["enabled"]

        for tool_cls in ALL_TOOLS:
            tool = tool_cls()
            if tool.name in enabled_tools:
                tools[tool.name] = tool

        return tools

    def _build_chat_messages(self, context: SessionContext) -> List[Dict[str, Any]]:
        """构建大模型所需的消息格式"""
        messages = []
        for msg in context.get_messages():
            message_dict = {
                "role": msg.role,
                "content": msg.content
            }

            # 添加工具调用信息
            if msg.tool_call:
                message_dict["tool_calls"] = msg.tool_call

            # 添加工具返回结果信息
            if msg.tool_result:
                message_dict["tool_call_id"] = msg.tool_result.get("tool_call_id")
                message_dict["name"] = msg.tool_result.get("name")

            messages.append(message_dict)

        return messages

    def _handle_function_call(self, function_call: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """处理工具调用，执行对应工具并返回结果"""
        tool_name = function_call.get("name")
        arguments = function_call.get("arguments", "{}")

        # 解析参数
        try:
            params = json.loads(arguments)
        except json.JSONDecodeError:
            return "", f"工具调用参数解析失败：arguments不是有效的JSON格式", {}

        # 检查工具是否存在
        if tool_name not in self.tools:
            return "", f"未知工具：{tool_name}", {}

        tool = self.tools[tool_name]

        # 验证参数
        if not tool.validate_parameters(params):
            return "", f"工具{tool_name}参数验证失败", {}

        # 执行工具
        try:
            result = tool.execute(params)
            return tool_name, result, params
        except Exception as e:
            return "", f"工具{tool_name}执行失败：{str(e)}", {}

    def chat(self, session_context: SessionContext, user_message: str, tool_call_enabled: bool = True) -> ChatResponse:
        """
        处理用户消息，返回回答（ReAct范式实现）
        支持多轮思考-行动循环和并行工具调用
        :param session_context: 会话上下文
        :param user_message: 用户消息内容
        :param tool_call_enabled: 是否启用工具调用
        :return: ChatResponse对象
        """
        # 添加用户消息到上下文
        user_msg = Message(
            role="user",
            content=user_message
        )
        session_context.add_message(user_msg)

        # 记录所有工具调用信息
        all_tool_calls = []
        all_tool_results = []
        max_iterations = AGENT_CONFIG["react"]["max_iterations"]
        enable_parallel = AGENT_CONFIG["react"]["enable_parallel_tools"]

        try:
            # ReAct思考-行动循环
            for iteration in range(max_iterations):
                # 构建消息
                messages = self._build_chat_messages(session_context)

                # 调用大模型
                create_kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_p": self.top_p,
                    "stream": False
                }

                # 如果启用工具调用，添加tools参数
                if tool_call_enabled and self.tool_definitions:
                    create_kwargs["tools"] = self.tool_definitions
                    create_kwargs["tool_choice"] = "auto" if iteration < max_iterations -1 else "none"

                response = self.client.chat.completions.create(**create_kwargs)
                choice = response.choices[0]
                finish_reason = choice.finish_reason

                # 情况1：没有工具调用，直接返回最终回答
                if finish_reason != "tool_calls" or not choice.message.tool_calls:
                    final_answer = choice.message.content
                    assistant_msg = Message(
                        role="assistant",
                        content=final_answer
                    )
                    session_context.add_message(assistant_msg)

                    # 构造返回结果
                    return ChatResponse(
                        session_id=session_context.session_id,
                        answer=final_answer,
                        is_tool_call=len(all_tool_calls) > 0,
                        tool_name=all_tool_calls[0]["name"] if len(all_tool_calls) == 1 else None,
                        tool_params=all_tool_calls[0]["parameters"] if len(all_tool_calls) == 1 else None,
                        tool_result=all_tool_results[0] if len(all_tool_results) == 1 else None,
                        metadata={
                            "iterations": iteration + 1,
                            "tool_calls": all_tool_calls,
                            "tool_results": all_tool_results
                        }
                    )

                # 情况2：需要调用工具
                tool_calls = choice.message.tool_calls
                tool_call_count = len(tool_calls)

                # 添加助手的工具调用消息
                assistant_msg = Message(
                    role="assistant",
                    content=choice.message.content or "",
                    tool_call={
                        "id": tool_calls[0].id if tool_call_count == 1 else None,
                        "type": "function",
                        "function": tool_calls[0].function.dict() if tool_call_count == 1 else None,
                        "parallel_calls": [tc.dict() for tc in tool_calls] if tool_call_count > 1 else None
                    }
                )
                session_context.add_message(assistant_msg)

                # 执行所有工具调用（支持并行）
                current_tool_results = []
                for tool_call in tool_calls:
                    function_call = tool_call.function
                    tool_name, tool_result, tool_params = self._handle_function_call(function_call)

                    # 记录工具调用信息
                    call_info = {
                        "id": tool_call.id,
                        "name": tool_name,
                        "parameters": tool_params,
                        "result": tool_result
                    }
                    all_tool_calls.append(call_info)
                    all_tool_results.append(tool_result)
                    current_tool_results.append(call_info)

                # 添加工具返回结果消息（每个工具调用对应一个tool消息）
                for result_info in current_tool_results:
                    tool_msg = Message(
                        role="tool",
                        content=result_info["result"],
                        tool_result={
                            "tool_call_id": result_info["id"],
                            "name": result_info["name"],
                            "result": result_info["result"]
                        }
                    )
                    session_context.add_message(tool_msg)

                # 继续下一轮迭代，让大模型基于工具结果继续思考

            # 达到最大迭代次数，强制返回
            final_answer = "抱歉，我无法在有限步骤内回答您的问题，请重新提问。"
            assistant_msg = Message(
                role="assistant",
                content=final_answer
            )
            session_context.add_message(assistant_msg)

            return ChatResponse(
                session_id=session_context.session_id,
                answer=final_answer,
                is_tool_call=len(all_tool_calls) > 0,
                metadata={
                    "iterations": max_iterations,
                    "tool_calls": all_tool_calls,
                    "tool_results": all_tool_results,
                    "max_iterations_reached": True
                }
            )

        except Exception as e:
            error_msg = f"处理请求时发生错误：{str(e)}"
            error_msg = Message(
                role="assistant",
                content=error_msg
            )
            session_context.add_message(error_msg)

            return ChatResponse(
                session_id=session_context.session_id,
                answer=error_msg.content,
                is_tool_call=len(all_tool_calls) > 0,
                metadata={
                    "error": str(e),
                    "tool_calls": all_tool_calls
                }
            )


# 全局Agent实例
agent = Agent()
