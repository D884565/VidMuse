import json
import os
import time
import asyncio
import threading
from typing import List, Dict, Any, Optional, Tuple
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv
from .dto.response import Message, ChatResponse
from ..tools.base import BaseSearchTool
from ..tools import ALL_TOOLS
from .context import SessionContext
from ..agent_config import AGENT_CONFIG
from .trace_storage import trace_storage
from backend.v1.app.config.config import settings

load_dotenv()

# 系统提示词
system_prompt = AGENT_CONFIG["system_prompt"]
tracing_config = AGENT_CONFIG.get("tracing", {})


class Agent:
    """Agent核心类，负责处理对话、工具调用和回答生成
    简化版本：逻辑更清晰，集成观测系统，自动落库推理轨迹
    """

    def __init__(self):
        # 初始化大模型客户端
        self.api_key = settings.DOUBAO_SEED_API_KEY or os.getenv("DOUBAO_SEED_API_KEY")
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.model_config = AGENT_CONFIG["model"]
        self.react_config = AGENT_CONFIG["react"]
        self.enabled_tools = AGENT_CONFIG["tools"]["enabled"]
        self.tracing_config = tracing_config

        self.client = Ark(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # 加载工具
        self.tools: Dict[str, BaseSearchTool] = self._load_tools()
        self.tool_definitions = [tool.get_function_definition() for tool in self.tools.values()]

        # 初始化异步事件循环（用于同步环境下的异步保存）
        self._loop = None
        if self.tracing_config.get("async_save", True):
            self._init_event_loop()

    def _init_event_loop(self):
        """初始化事件循环，处理同步环境下的异步任务"""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，创建一个新的
            self._loop = asyncio.new_event_loop()
            # 启动后台线程运行事件循环
            threading.Thread(target=self._run_event_loop, daemon=True).start()

    def _run_event_loop(self):
        """在后台线程中运行事件循环"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _load_tools(self) -> Dict[str, BaseSearchTool]:
        """加载配置中启用的工具"""
        return {
            tool_cls.name: tool_cls()
            for tool_cls in ALL_TOOLS
            if tool_cls.name in self.enabled_tools
        }

    def _build_chat_messages(self, context: SessionContext) -> List[Dict[str, Any]]:
        """构建大模型所需的消息格式（简化版，使用Message.to_dict）"""
        return [msg.to_dict() for msg in context.get_messages()]

    def _handle_function_call(self, function_call: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """处理工具调用，执行对应工具并返回结果"""
        tool_name = function_call.get("name")
        arguments = function_call.get("arguments", "{}")

        # 解析参数
        try:
            params = json.loads(arguments)
        except json.JSONDecodeError:
            return "", "工具调用参数解析失败：arguments不是有效的JSON格式", {}

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

    def _create_chat_response(
        self,
        session_context: SessionContext,
        final_answer: str,
        iterations: int,
        all_tool_calls: List[Dict[str, Any]],
        all_tool_results: List[str],
        success: bool = True,
        error_msg: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """创建统一的ChatResponse对象（简化重复逻辑）"""
        # 添加助手消息到上下文
        assistant_msg = Message(
            role="assistant",
            content=final_answer
        )
        session_context.add_message(assistant_msg)

        # 构造基础元数据
        base_metadata = {
            "iterations": iterations,
            "tool_calls": all_tool_calls,
            "tool_results": all_tool_results
        }
        if metadata:
            base_metadata.update(metadata)

        # 构造返回结果
        response = ChatResponse(
            session_id=session_context.session_id,
            answer=final_answer,
            is_tool_call=len(all_tool_calls) > 0,
            tool_name=all_tool_calls[0]["name"] if len(all_tool_calls) == 1 else None,
            tool_params=all_tool_calls[0]["parameters"] if len(all_tool_calls) == 1 else None,
            tool_result=all_tool_results[0] if len(all_tool_results) == 1 else None,
            metadata=base_metadata
        )

        # 保存推理轨迹（如果启用）
        if self.tracing_config.get("enabled", True):
            # 找到用户原始消息
            messages = session_context.get_messages()
            user_message = messages[0].content if len(messages) == 1 else messages[-len(all_tool_calls)*2 - 2].content

            save_kwargs = {
                "session_context": session_context,
                "user_message": user_message,
                "final_answer": final_answer,
                "iterations": iterations,
                "all_tool_calls": all_tool_calls,
                "all_tool_results": all_tool_results,
                "success": success,
                "error_msg": error_msg
            }

            if self.tracing_config.get("async_save", True):
                # 异步保存
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._save_trace(**save_kwargs), self._loop)
                else:
                    # 事件循环不可用，降级为同步保存
                    asyncio.run(self._save_trace(**save_kwargs))
            else:
                # 同步保存
                asyncio.run(self._save_trace(**save_kwargs))

        return response

    async def _save_trace(
        self,
        session_context: SessionContext,
        user_message: str,
        final_answer: str,
        iterations: int,
        all_tool_calls: List[Dict[str, Any]],
        all_tool_results: List[str],
        success: bool = True,
        error_msg: Optional[str] = None
    ):
        """保存推理轨迹到数据库"""
        try:
            # 构建消息历史
            messages_history = [msg.to_dict() for msg in session_context.get_messages()]

            # 从上下文中获取额外信息
            user_id = getattr(session_context, "user_id", None)
            project_id = getattr(session_context, "project_id", None)

            # 类型转换：user_id可能是str，转为int
            if user_id is not None and isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
            if project_id is not None and isinstance(project_id, str) and project_id.isdigit():
                project_id = int(project_id)

            # 系统提示词
            prompt = system_prompt if self.tracing_config.get("save_system_prompt", True) else ""

            await trace_storage.save_trace(
                session_id=session_context.session_id,
                user_id=user_id,
                project_id=project_id,
                user_input=user_message,
                system_prompt=prompt,
                model=self.model_config["name"],
                temperature=self.model_config["temperature"],
                max_tokens=self.model_config["max_tokens"],
                top_p=self.model_config["top_p"],
                messages_history=messages_history,
                iterations=iterations,
                tool_calls=all_tool_calls,
                tool_results=all_tool_results,
                final_answer=final_answer,
                cost_time=time.time() - getattr(self, "_start_time", time.time()),
                success=success,
                error_msg=error_msg,
                meta_data=session_context.metadata
            )
        except Exception as e:
            # 轨迹保存失败不影响主流程
            print(f"保存Agent轨迹失败: {str(e)}")

    def chat(self, session_context: SessionContext, user_message: str, tool_call_enabled: bool = True) -> ChatResponse:
        """
        处理用户消息，返回回答（ReAct范式实现）
        支持多轮思考-行动循环和并行工具调用
        :param session_context: 会话上下文
        :param user_message: 用户消息内容
        :param tool_call_enabled: 是否启用工具调用
        :return: ChatResponse对象
        """
        # 记录开始时间
        self._start_time = time.time()

        # 添加用户消息到上下文
        user_msg = Message(role="user", content=user_message)
        session_context.add_message(user_msg)

        # 初始化变量
        all_tool_calls = []
        all_tool_results = []
        max_iterations = self.react_config["max_iterations"]

        try:
            # ReAct思考-行动循环
            for iteration in range(max_iterations):
                # 构建消息
                messages = self._build_chat_messages(session_context)

                # 调用大模型
                create_kwargs = {
                    "model": self.model_config["name"],
                    "messages": messages,
                    "temperature": self.model_config["temperature"],
                    "max_tokens": self.model_config["max_tokens"],
                    "top_p": self.model_config["top_p"],
                    "stream": False
                }

                # 添加工具调用参数
                if tool_call_enabled and self.tool_definitions:
                    create_kwargs["tools"] = self.tool_definitions
                    create_kwargs["tool_choice"] = "auto" if iteration < max_iterations - 1 else "none"

                response = self.client.chat.completions.create(**create_kwargs)
                choice = response.choices[0]

                # 没有工具调用，直接返回最终回答
                if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                    return self._create_chat_response(
                        session_context=session_context,
                        final_answer=choice.message.content or "",
                        iterations=iteration + 1,
                        all_tool_calls=all_tool_calls,
                        all_tool_results=all_tool_results,
                        success=True
                    )

                # 处理工具调用
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

                # 执行所有工具调用
                current_tool_results = []
                for tool_call in tool_calls:
                    tool_name, tool_result, tool_params = self._handle_function_call(tool_call.function)

                    call_info = {
                        "id": tool_call.id,
                        "name": tool_name,
                        "parameters": tool_params,
                        "result": tool_result
                    }
                    all_tool_calls.append(call_info)
                    all_tool_results.append(tool_result)
                    current_tool_results.append(call_info)

                # 添加工具返回结果消息
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

            # 达到最大迭代次数
            final_answer = "抱歉，我无法在有限步骤内回答您的问题，请重新提问。"
            return self._create_chat_response(
                session_context=session_context,
                final_answer=final_answer,
                iterations=max_iterations,
                all_tool_calls=all_tool_calls,
                all_tool_results=all_tool_results,
                success=False,
                error_msg="达到最大迭代次数",
                metadata={"max_iterations_reached": True}
            )

        except Exception as e:
            error_msg = f"处理请求时发生错误：{str(e)}"
            return self._create_chat_response(
                session_context=session_context,
                final_answer=error_msg,
                iterations=len(all_tool_calls) or 1,
                all_tool_calls=all_tool_calls,
                all_tool_results=all_tool_results,
                success=False,
                error_msg=str(e),
                metadata={"error": str(e)}
            )


# 全局Agent实例
agent = Agent()
