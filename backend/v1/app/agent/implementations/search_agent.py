"""通用搜索Agent实现"""
from typing import Optional, Dict, Any, List
from .react_agent import ReActAgent
from ..config import AGENT_CONFIG
from backend.v1.app.search import SearchEngine, SearchQuery
from ..core.tool import BaseTool
import logging

logger = logging.getLogger(__name__)

class SearchAgent(ReActAgent):
    """
    通用搜索Agent
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
        search_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化搜索Agent
        :param agent_id: Agent唯一标识
        :param name: Agent名称
        :param description: Agent描述
        :param config: 自定义配置
        :param model: 使用的模型
        :param max_iterations: 最大迭代次数
        :param search_config: 检索引擎配置
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            config=config,
            model=model,
            max_iterations=max_iterations
        )

        # 初始化检索引擎
        try:
            self.search_engine = SearchEngine(search_config)
            logger.info("SearchAgent初始化检索引擎成功")
        except Exception as e:
            logger.error(f"SearchAgent初始化检索引擎失败: {str(e)}", exc_info=True)
            self.search_engine = None

        # 注册搜索工具
        class SearchTool(BaseTool):
            name = "search_tool"
            description = "搜索相关信息，回答用户问题，支持检索知识库、数据库等多种数据源"
            parameters_schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要搜索的查询文本"
                    }
                },
                "required": ["query"]
            }

            def execute(tool_self, parameters: Dict[str, Any]) -> str:
                results = self._search_tool(parameters["query"], **(parameters.get("context", {})))
                return str(results)

        self.tool_system.register_tool(SearchTool())

    def _search_tool(self, query: str, **kwargs) -> List[Dict]:
        """
        检索工具，供Agent调用
        :param query: 查询文本
        :param kwargs: 额外参数（user_id, project_id, session_id等）
        :return: 检索结果列表
        """
        if not self.search_engine:
            logger.warning("检索引擎未初始化，无法执行检索")
            return []

        try:
            # 构建检索查询
            search_query = SearchQuery(
                query_text=query,
                top_k=10,
                metadata=kwargs
            )

            # 执行检索
            results = self.search_engine.search(search_query)

            # 转换为字典格式返回给Agent
            return [
                {
                    "id": result.result_id,
                    "content": result.content,
                    "score": result.score,
                    "source": result.source,
                    "source_type": result.source_type,
                    "metadata": result.metadata
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"检索工具执行失败: {str(e)}", exc_info=True)
            return []

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
