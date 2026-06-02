"""Agent抽象基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseAgent(ABC):
    """
    Agent抽象基类，定义所有Agent的通用接口
    所有业务Agent都必须继承此类并实现抽象方法
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id  # Agent唯一标识
        self.name = name          # Agent名称
        self.description = description  # Agent描述
        self.config = config or {}      # Agent自定义配置

        # 核心组件（由子类初始化）
        self.memory = None       # 记忆系统
        self.tool_system = None  # 工具系统
        self.context_builder = None  # 上下文构建器

    @abstractmethod
    def think(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        思考阶段：分析用户查询，制定执行计划
        :param query: 用户查询内容
        :param context: 额外上下文信息
        :return: 思考结果，包含下一步行动决策
        """
        pass

    @abstractmethod
    def act(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """
        行动阶段：执行思考阶段决定的操作
        :param thought: 思考结果
        :return: 行动执行结果
        """
        pass

    @abstractmethod
    def observe(self, action_result: Dict[str, Any]) -> None:
        """
        观察阶段：记录行动结果，更新记忆
        :param action_result: 行动执行结果
        """
        pass

    @abstractmethod
    def generate_response(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        生成最终回答
        :param query: 用户查询内容
        :param context: 额外上下文信息
        :return: 最终回答内容
        """
        pass

    @abstractmethod
    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        完整执行流程：思考 -> 行动 -> 观察 -> 回答
        :param query: 用户查询内容
        :param context: 额外上下文信息
        :return: 执行结果，包含状态、回答、迭代次数等信息
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """获取Agent当前状态"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "has_memory": self.memory is not None,
            "has_tool_system": self.tool_system is not None,
            "has_context_builder": self.context_builder is not None
        }
