"""ReAct范式Agent实现"""
import os
import json
import time
import asyncio
from typing import Any, Dict, List, Optional
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv
from ..core.base_agent import BaseAgent
from .short_term_memory import ShortTermMemory
from .tool_system import ToolSystem
from .prompt_builder import PromptBuilder
from ..config import AGENT_CONFIG

# 导入TraceStorage
try:
    from backend.v1.app.agent.trace.trace_storage import trace_storage
    HAS_TRACE_STORAGE = True
except ImportError:
    HAS_TRACE_STORAGE = False

load_dotenv()

class ReActAgent(BaseAgent):
    """
    基于ReAct范式的Agent实现
    支持多轮思考-行动-观察循环，工具调用，记忆管理
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None
    ):
        super().__init__(agent_id, name, description, config)

        # 模型配置
        self.model = model or AGENT_CONFIG["model"]["default_model"]
        self.model_config = {
            "temperature": AGENT_CONFIG["model"]["temperature"],
            "max_tokens": AGENT_CONFIG["model"]["max_tokens"],
            "top_p": AGENT_CONFIG["model"]["top_p"]
        }
        self.max_iterations = max_iterations or AGENT_CONFIG["react"]["max_iterations"]

        # 初始化核心组件
        self.memory = ShortTermMemory()
        self.tool_system = ToolSystem()
        self.context_builder = PromptBuilder()

        # 初始化大模型客户端
        self._init_llm_client()

        # 追踪配置
        self.tracing_config = AGENT_CONFIG["tracing"]

    def _do_save_trace(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
        messages_history: List[Dict[str, Any]],
        iterations: int,
        all_tool_calls: List[Dict[str, Any]],
        all_tool_results: List[str],
        final_answer: str,
        success: bool = True,
        error_msg: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ):
        """同步保存推理轨迹"""
        if not HAS_TRACE_STORAGE or not self.tracing_config.get("enabled", True):
            return

        try:
            trace_storage.save_trace(
                session_id=session_id,
                user_input=user_input,
                system_prompt=system_prompt if self.tracing_config.get("save_system_prompt", True) else "",
                model=self.model,
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
                user_id=user_id,
                project_id=project_id,
                meta_data=meta_data
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"保存Agent轨迹失败: {str(e)}")

    def _save_trace(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
        messages_history: List[Dict[str, Any]],
        iterations: int,
        all_tool_calls: List[Dict[str, Any]],
        all_tool_results: List[str],
        final_answer: str,
        success: bool = True,
        error_msg: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ):
        """保存推理轨迹，支持同步和异步"""
        if not HAS_TRACE_STORAGE or not self.tracing_config.get("enabled", True):
            return

        save_kwargs = {
            "session_id": session_id,
            "user_input": user_input,
            "system_prompt": system_prompt,
            "messages_history": messages_history,
            "iterations": iterations,
            "all_tool_calls": all_tool_calls,
            "all_tool_results": all_tool_results,
            "final_answer": final_answer,
            "success": success,
            "error_msg": error_msg,
            "user_id": user_id,
            "project_id": project_id,
            "meta_data": meta_data
        }

        # 直接同步调用，避免事件循环问题
        self._do_save_trace(**save_kwargs)


    def _init_llm_client(self):
        """初始化大模型客户端"""
        self.api_key = os.getenv("DOUBAO_SEED_API_KEY")
        if not self.api_key:
            raise ValueError("DOUBAO_SEED_API_KEY环境变量未配置，无法初始化Agent")

        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
        self.client = Ark(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _call_llm(self, messages: List[Dict[str, str]], enable_tool_calls: bool = True) -> Dict[str, Any]:
        """调用大模型"""
        create_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.model_config["temperature"],
            "max_tokens": self.model_config["max_tokens"],
            "top_p": self.model_config["top_p"],
            "stream": False
        }

        # 添加工具调用参数
        if enable_tool_calls and self.tool_system.get_tool_definitions():
            create_kwargs["tools"] = self.tool_system.get_tool_definitions()
            create_kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**create_kwargs)
            choice = response.choices[0]

            # 解析返回结果
            result = {
                "content": choice.message.content or "",
                "tool_calls": []
            }

            # 处理工具调用
            if choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    if hasattr(tool_call.function, 'dict'):
                        function_dict = tool_call.function.dict()
                    else:
                        function_dict = {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }

                    # 解析参数
                    try:
                        parameters = json.loads(function_dict["arguments"])
                    except json.JSONDecodeError:
                        parameters = {}

                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "name": function_dict["name"],
                        "parameters": parameters
                    })

            return result

        except Exception as e:
            raise RuntimeError(f"调用大模型失败: {str(e)}")

    def think(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """思考阶段：调用大模型分析问题，决定下一步行动"""
        messages = self.context_builder.build_chat_messages(
            agent=self,
            query=query,
            context=context,
            include_history=True
        )

        # 调用大模型
        response = self._call_llm(messages)

        # 记录思考结果到记忆
        self.memory.add({
            "type": "thought",
            "content": response["content"],
            "tool_calls": response["tool_calls"]
        })

        return response

    def act(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """行动阶段：执行工具调用"""
        tool_calls = thought.get("tool_calls", [])
        if not tool_calls:
            return {
                "type": "response",
                "content": thought.get("content", "")
            }

        # 执行所有工具调用
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            parameters = tool_call["parameters"]

            result = self.tool_system.execute_tool(tool_name, parameters)
            results.append({
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result
            })

        # 记录工具调用结果到记忆
        self.memory.add({
            "type": "tool_results",
            "content": results
        })

        return {
            "type": "tool_results",
            "content": results
        }

    def observe(self, action_result: Dict[str, Any]) -> None:
        """观察阶段：已经在act中记录到记忆，这里可以扩展其他观察逻辑"""
        pass

    def generate_response(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """生成最终回答"""
        messages = self.context_builder.build_chat_messages(
            agent=self,
            query=query,
            context=context,
            include_history=True
        )

        # 调用大模型生成最终回答，禁用工具调用
        response = self._call_llm(messages, enable_tool_calls=False)
        return response["content"]

    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """完整的ReAct执行流程"""
        start_time = time.time()
        self._start_time = start_time

        # 记录用户查询到记忆
        self.memory.add({
            "type": "user_query",
            "content": query,
            "context": context
        })

        iterations = 0
        final_answer = ""
        success = False
        error_msg = None

        # 收集轨迹数据
        all_tool_calls = []
        all_tool_results = []
        system_prompt = self.context_builder.build_system_prompt(self)

        # 从context中获取会话和用户信息
        context = context or {}
        session_id = context.get("session_id", f"session_{int(time.time())}")
        user_id = context.get("user_id")
        project_id = context.get("project_id")
        meta_data = context.get("meta_data", {})

        try:
            while iterations < self.max_iterations:
                iterations += 1
                # 思考
                thought = self.think(query, context)

                # 不需要工具调用，直接返回回答
                if not thought.get("tool_calls"):
                    final_answer = thought.get("content", "")
                    success = True
                    break

                # 行动
                action_result = self.act(thought)

                # 收集工具调用和结果
                if action_result.get("type") == "tool_results":
                    for result in action_result["content"]:
                        all_tool_calls.append({
                            "name": result["tool_name"],
                            "parameters": result["parameters"],
                            "result": result["result"]
                        })
                        all_tool_results.append(result["result"])

                # 观察
                self.observe(action_result)

            # 达到最大迭代次数
            if not success and iterations >= self.max_iterations:
                final_answer = "抱歉，我无法在有限步骤内回答您的问题，请重新提问。"
                error_msg = "达到最大迭代次数"

            # 如果有工具调用但没有生成回答，生成最终回答
            if not final_answer and iterations > 0:
                final_answer = self.generate_response(query, context)
                success = True

            # 保存回答到记忆
            self.memory.add({
                "type": "agent_response",
                "content": final_answer,
                "success": success,
                "iterations": iterations,
                "time_cost": time.time() - start_time
            })

            # 构建消息历史
            messages_history = []
            for memory in self.memory.get_recent(100):
                content = memory["content"]
                if isinstance(content, dict):
                    if content.get("type") == "user_query":
                        messages_history.append({"role": "user", "content": content["content"]})
                    elif content.get("type") == "agent_response":
                        messages_history.append({"role": "assistant", "content": content["content"]})
                    elif content.get("type") == "tool_results":
                        tool_prompt = self.context_builder.build_tool_prompt(content["content"])
                        messages_history.append({"role": "user", "content": tool_prompt})
                    elif content.get("type") == "thought":
                        # 思考过程不加入消息历史
                        pass

            # 保存轨迹
            self._save_trace(
                session_id=session_id,
                user_input=query,
                system_prompt=system_prompt,
                messages_history=messages_history,
                iterations=iterations,
                all_tool_calls=all_tool_calls,
                all_tool_results=all_tool_results,
                final_answer=final_answer,
                success=success,
                error_msg=error_msg,
                user_id=user_id,
                project_id=project_id,
                meta_data=meta_data
            )

            return {
                "success": success,
                "answer": final_answer,
                "iterations": iterations,
                "agent_id": self.agent_id,
                "time_cost": time.time() - start_time,
                "error": error_msg,
                "session_id": session_id
            }

        except Exception as e:
            error_msg = f"Agent执行出错: {str(e)}"
            self.memory.add({
                "type": "error",
                "content": error_msg
            })
            # 错误情况下也保存轨迹
            messages_history = []
            for memory in self.memory.get_recent(100):
                content = memory["content"]
                if isinstance(content, dict):
                    if content.get("type") == "user_query":
                        messages_history.append({"role": "user", "content": content["content"]})
                    elif content.get("type") == "agent_response":
                        messages_history.append({"role": "assistant", "content": content["content"]})
                    elif content.get("type") == "tool_results":
                        tool_prompt = self.context_builder.build_tool_prompt(content["content"])
                        messages_history.append({"role": "user", "content": tool_prompt})
                    elif content.get("type") == "thought":
                        pass

            self._save_trace(
                session_id=session_id,
                user_input=query,
                system_prompt=system_prompt,
                messages_history=messages_history,
                iterations=iterations,
                all_tool_calls=all_tool_calls,
                all_tool_results=all_tool_results,
                final_answer=error_msg,
                success=False,
                error_msg=error_msg,
                user_id=user_id,
                project_id=project_id,
                meta_data=meta_data
            )

            return {
                "success": False,
                "answer": f"处理请求时发生错误：{str(e)}",
                "iterations": iterations,
                "agent_id": self.agent_id,
                "time_cost": time.time() - start_time,
                "error": str(e),
                "session_id": session_id
            }
