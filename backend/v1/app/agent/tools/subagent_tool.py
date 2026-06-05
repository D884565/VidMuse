"""子Agent创建工具
允许主Agent动态创建子Agent并委派任务执行，支持任务分解、多视角分析等场景
"""
from typing import Dict, Any, List
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from ..core.tool import BaseTool
from ..utils.tool_registry import register_tool, ToolRegistry
from ..implementations.react_agent import ReActAgent
from ..config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# 安全配置
SUBAGENT_CONFIG = {
    "max_iterations": 5,        # 子Agent最大迭代次数，防止无限循环
    "max_execution_time": 30,   # 子Agent最大执行时间（秒）
    "max_level": 1,             # 最大Agent层级，防止递归创建
    "allowed_tools": [          # 子Agent允许使用的工具白名单
        "query_video_library",
        "search_tool"
        # 注意：不包含create_subagent，防止递归创建
    ]
}

@register_tool
class CreateSubagentTool(BaseTool):
    """
    创建子Agent并委派任务执行的工具
    适用于复杂任务分解、多视角分析、专业领域任务处理等场景
    """
    name: str = "create_subagent"
    description: str = "创建一个专用子Agent并委派任务执行，支持复杂任务分解、多视角分析。子Agent拥有独立的角色和工具集，执行完成后返回结果。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "子Agent的唯一标识，由调用者指定，用于区分不同子Agent，例如：'user_analysis_expert_001'"
            },
            "name": {
                "type": "string",
                "description": "子Agent的名称，描述其角色，例如：'用户需求分析专家', '技术方案评审专家', '文案撰写助手'"
            },
            "description": {
                "type": "string",
                "description": "子Agent的详细描述，说明其职责、能力范围和工作风格，例如：'你是专业的用户需求分析专家，擅长从用户视角分析产品需求，输出结构化的需求分析报告'"
            },
            "task": {
                "type": "string",
                "description": "需要子Agent执行的具体任务，详细描述任务目标、要求和输出格式"
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"子Agent可以使用的工具名称列表，默认为空（只能回答问题，不能调用工具）。可用工具包括：{', '.join(SUBAGENT_CONFIG['allowed_tools'])}"
            },
            "model": {
                "type": "string",
                "description": "子Agent使用的模型，默认使用系统默认模型"
            },
            "max_iterations": {
                "type": "integer",
                "description": f"子Agent的最大迭代次数，默认3次，最大不超过{SUBAGENT_CONFIG['max_iterations']}次，防止无限循环",
                "default": 3,
                "minimum": 1,
                "maximum": SUBAGENT_CONFIG["max_iterations"]
            },
            "output_format": {
                "type": "string",
                "description": "要求子Agent输出的格式，例如：'JSON', 'Markdown', '纯文本'等，默认纯文本",
                "default": "纯文本"
            }
        },
        "required": ["agent_id", "name", "task"]
    }

    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和标准化参数
        :param parameters: 输入参数
        :return: 标准化后的参数
        """
        # 验证必填参数
        required_fields = ["agent_id", "name", "task"]
        for field in required_fields:
            if field not in parameters:
                raise ValueError(f"缺少必填参数：{field}")

        # 验证工具权限
        requested_tools = parameters.get("tools", [])
        invalid_tools = [tool for tool in requested_tools if tool not in SUBAGENT_CONFIG["allowed_tools"]]
        if invalid_tools:
            raise ValueError(f"工具 {', '.join(invalid_tools)} 不允许被子Agent使用，允许的工具：{', '.join(SUBAGENT_CONFIG['allowed_tools'])}")

        # 验证迭代次数
        max_iterations = parameters.get("max_iterations", 3)
        if max_iterations < 1 or max_iterations > SUBAGENT_CONFIG["max_iterations"]:
            raise ValueError(f"最大迭代次数必须在1到{SUBAGENT_CONFIG['max_iterations']}之间")

        # 构建任务提示词
        task = parameters["task"]
        output_format = parameters.get("output_format", "纯文本")
        if output_format.lower() == "json":
            task += "\n\n要求：输出必须是合法的JSON格式，不要包含任何其他解释性文字。"
        elif output_format.lower() == "markdown":
            task += "\n\n要求：输出使用Markdown格式，结构清晰。"

        parameters["task"] = task
        return parameters

    def _create_subagent(self, parameters: Dict[str, Any]) -> ReActAgent:
        """
        创建子Agent实例
        :param parameters: 配置参数
        :return: 初始化好的ReActAgent实例
        """
        agent_id = parameters["agent_id"]
        name = parameters["name"]
        description = parameters.get("description", f"这是{name}，专注于执行特定任务。")
        model = parameters.get("model")
        max_iterations = parameters.get("max_iterations", 3)

        # 创建子Agent
        subagent = ReActAgent(
            agent_id=agent_id,
            name=name,
            description=description,
            model=model,
            max_iterations=max_iterations
        )

        # 注册指定的工具
        requested_tools = parameters.get("tools", [])
        for tool_name in requested_tools:
            if tool_name in SUBAGENT_CONFIG["allowed_tools"]:
                try:
                    tool_class = ToolRegistry.get(tool_name)
                    if tool_class:
                        subagent.tool_system.register_tool(tool_class())
                        logger.info(f"子Agent {agent_id} 注册工具成功：{tool_name}")
                except Exception as e:
                    logger.warning(f"子Agent {agent_id} 注册工具失败 {tool_name}: {str(e)}")

        return subagent

    def _run_subagent_task(self, subagent: ReActAgent, task: str) -> Dict[str, Any]:
        """
        执行子Agent任务（同步执行）
        :param subagent: 子Agent实例
        :param task: 任务内容
        :return: 执行结果
        """
        try:
            result = subagent.run(task)
            return {
                "success": result.get("success", False),
                "answer": result.get("answer", ""),
                "iterations": result.get("iterations", 0),
                "time_cost": result.get("time_cost", 0),
                "error": result.get("error")
            }
        except Exception as e:
            logger.error(f"子Agent {subagent.agent_id} 执行任务失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "answer": "",
                "iterations": 0,
                "time_cost": 0,
                "error": str(e)
            }

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行工具逻辑：创建子Agent并执行任务
        :param parameters: 工具参数
        :return: JSON格式的执行结果
        """
        try:
            # 参数验证和标准化
            params = self._validate_parameters(parameters)
            agent_id = params["agent_id"]
            task = params["task"]

            logger.info(f"开始创建子Agent: {agent_id}, 任务: {task[:100]}...")

            # 创建子Agent
            subagent = self._create_subagent(params)

            # 执行任务（带超时控制）
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(self._run_subagent_task, subagent, task)

            try:
                result = future.result(timeout=SUBAGENT_CONFIG["max_execution_time"])
            except TimeoutError:
                result = {
                    "success": False,
                    "answer": "",
                    "iterations": 0,
                    "time_cost": SUBAGENT_CONFIG["max_execution_time"],
                    "error": f"任务执行超时，超过最大限制{SUBAGENT_CONFIG['max_execution_time']}秒"
                }
                logger.warning(f"子Agent {agent_id} 执行超时")
            finally:
                executor.shutdown(wait=False)

            # 构建返回结果
            response = {
                "agent_id": agent_id,
                "name": params["name"],
                "task": task,
                "success": result["success"],
                "result": result["answer"],
                "iterations": result["iterations"],
                "time_cost": round(result["time_cost"], 2),
                "error": result["error"]
            }

            # 清理子Agent资源（帮助GC）
            del subagent

            logger.info(f"子Agent {agent_id} 执行完成，成功: {result['success']}, 耗时: {result['time_cost']}s")

            return json.dumps(response, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"创建子Agent失败: {str(e)}", exc_info=True)
            error_response = {
                "success": False,
                "agent_id": parameters.get("agent_id", "unknown"),
                "error": str(e),
                "result": ""
            }
            return json.dumps(error_response, ensure_ascii=False)
