"""通用搜索Agent实现"""
from typing import Optional, Dict, Any, List
from .react_agent import ReActAgent
from .tool_system import ToolSystem
from ..config import AGENT_CONFIG

# 导入现有搜索工具
try:
    from backend.v1.app.search.tools import (
        BaseSearchTool,
        SemanticSearchTool,
        KeywordSearchTool,
        SQLQueryTool,
        HybridSearchTool,
        GeneralSearchTool,
        ALL_TOOLS
    )
    HAS_SEARCH_TOOLS = True
except ImportError:
    HAS_SEARCH_TOOLS = False


class SearchAgent(ReActAgent):
    """
    通用搜索Agent，集成所有搜索工具
    基于ReAct范式，支持多轮搜索和推理
    """

    def __init__(
        self,
        agent_id: str = "search_agent",
        name: str = "智能搜索助手",
        description: str = "擅长信息检索和问题解答的智能助手，可以调用多种搜索工具获取信息。",
        config: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None,
        enable_tools: Optional[List[str]] = None
    ):
        """
        初始化搜索Agent
        :param agent_id: Agent唯一标识
        :param name: Agent名称
        :param description: Agent描述
        :param config: 自定义配置
        :param model: 使用的模型
        :param max_iterations: 最大迭代次数
        :param enable_tools: 启用的工具列表，默认启用所有搜索工具
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            config=config,
            model=model,
            max_iterations=max_iterations
        )

        # 注册搜索工具
        if HAS_SEARCH_TOOLS:
            self._register_search_tools(enable_tools)

    def _register_search_tools(self, enable_tools: Optional[List[str]] = None) -> None:
        """注册搜索工具"""
        enabled_tools = enable_tools or []

        for tool_class in ALL_TOOLS:
            # 如果指定了启用列表，只注册列表中的工具
            if enabled_tools and tool_class.name not in enabled_tools:
                continue

            try:
                tool_instance = tool_class()
                self.tool_system.register_tool(tool_instance)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"注册工具 {tool_class.name} 失败: {str(e)}")

    def chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        tool_call_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        兼容原有Agent的chat接口，保持API一致性
        :param query: 用户查询
        :param session_id: 会话ID
        :param user_id: 用户ID
        :param project_id: 项目ID
        :param context: 额外上下文
        :param tool_call_enabled: 是否启用工具调用（兼容旧接口，当前未使用）
        :return: 回答结果
        """
        # 构建上下文
        run_context = context or {}
        if session_id:
            run_context["session_id"] = session_id
        if user_id:
            run_context["user_id"] = user_id
        if project_id:
            run_context["project_id"] = project_id

        # 调用父类run方法
        return self.run(query, run_context)


# 兼容原有全局Agent实例
try:
    search_agent = SearchAgent()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"初始化全局SearchAgent失败: {str(e)}")
    search_agent = None
