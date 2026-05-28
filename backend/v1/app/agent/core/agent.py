import json
import os
from typing import List, Dict, Any, Optional, Tuple
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv
from ..dto.response import Message, ChatResponse
from ..tools.base import BaseTool
from ..tools.rag_tool import RAGSearchTool
from .context import SessionContext
from ..config import AGENT_CONFIG, TOOL_CLASS_MAPPING

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

    def _load_tools(self) -> Dict[str, BaseTool]:
        """加载配置中启用的工具"""
        tools = {}
        enabled_tools = AGENT_CONFIG["tools"]["enabled"]

        for tool_name in enabled_tools:
            if tool_name not in TOOL_CLASS_MAPPING:
                continue

            # 动态导入工具类
            module_path, class_name = TOOL_CLASS_MAPPING[tool_name].rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            tool_class = getattr(module, class_name)
            tools[tool_name] = tool_class()

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
        处理用户消息，返回回答
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

        # 构建消息
        messages = self._build_chat_messages(session_context)

        # 调用大模型
        try:
            # 第一次调用，判断是否需要工具调用
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
                create_kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**create_kwargs)

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # 处理工具调用
            if finish_reason == "tool_calls" and choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0].function
                tool_name, tool_result, tool_params = self._handle_function_call(tool_call)

                if tool_name:
                    # 添加助手的工具调用消息
                    assistant_msg = Message(
                        role="assistant",
                        content="",
                        tool_call={
                            "id": choice.message.tool_calls[0].id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": tool_call.arguments
                            }
                        }
                    )
                    session_context.add_message(assistant_msg)

                    # 添加工具返回结果消息
                    tool_msg = Message(
                        role="tool",
                        content=tool_result,
                        tool_result={
                            "tool_call_id": choice.message.tool_calls[0].id,
                            "name": tool_name,
                            "result": tool_result
                        }
                    )
                    session_context.add_message(tool_msg)

                    # 再次调用大模型，传入工具结果
                    messages = self._build_chat_messages(session_context)
                    second_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=self.top_p,
                        stream=False
                    )

                    second_choice = second_response.choices[0]
                    final_answer = second_choice.message.content

                    # 添加最终回答到上下文
                    final_msg = Message(
                        role="assistant",
                        content=final_answer
                    )
                    session_context.add_message(final_msg)

                    return ChatResponse(
                        session_id=session_context.session_id,
                        answer=final_answer,
                        is_tool_call=True,
                        tool_name=tool_name,
                        tool_params=tool_params,
                        tool_result=tool_result
                    )

            # 不需要工具调用，直接返回回答
            final_answer = choice.message.content
            assistant_msg = Message(
                role="assistant",
                content=final_answer
            )
            session_context.add_message(assistant_msg)

            return ChatResponse(
                session_id=session_context.session_id,
                answer=final_answer,
                is_tool_call=False
            )

        except Exception as e:
            error_msg = f"处理请求时发生错误：{str(e)}"
            return ChatResponse(
                session_id=session_context.session_id,
                answer=error_msg,
                is_tool_call=False
            )


# 全局Agent实例
agent = Agent()
