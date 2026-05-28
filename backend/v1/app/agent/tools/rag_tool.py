from typing import Dict, Any
from .base import BaseTool
from ...search import SearchService
from ...search.config import RETRIEVAL_CONFIG
from ..config import AGENT_CONFIG


class RAGSearchTool(BaseTool):
    """RAG检索工具，用于查询知识库中的相关信息"""

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return "查询知识库中的相关信息，当回答问题需要最新的知识库内容或者特定领域知识时使用此工具。" \
               "如果问题涉及到内部文档、产品信息、业务规则等内容时必须使用此工具。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户的查询问题，需要清晰明确地描述要查询的内容"
                },
                "top_k": {
                    "type": "integer",
                    "description": f"返回的结果数量，默认{AGENT_CONFIG['tools']['rag_search']['default_top_k']}，"
                                   f"最大不超过{AGENT_CONFIG['tools']['rag_search']['max_top_k']}",
                    "default": AGENT_CONFIG["tools"]["rag_search"]["default_top_k"]
                }
            },
            "required": ["query"]
        }

    def __init__(self):
        self.search_service = SearchService()
        self.default_top_k = AGENT_CONFIG["tools"]["rag_search"]["default_top_k"]
        self.max_top_k = AGENT_CONFIG["tools"]["rag_search"]["max_top_k"]

    def execute(self, params: Dict[str, Any]) -> str:
        """执行RAG检索"""
        query = params.get("query", "")
        top_k = min(params.get("top_k", self.default_top_k), self.max_top_k)

        if not query:
            return "错误：查询内容不能为空"

        try:
            # 调用RAG检索服务
            result = self.search_service.search(query, top_k=top_k)

            if not result.success:
                return f"检索失败：{result.error_msg}"

            if not result.documents:
                return "未找到相关信息"

            # 格式化检索结果
            formatted_results = []
            for i, doc in enumerate(result.documents, 1):
                formatted_results.append(
                    f"[{i}] 来源: {doc.source_type}\n"
                    f"内容: {doc.content}\n"
                    f"相关度: {doc.score:.2f}\n"
                )

            return "检索到以下相关信息：\n\n" + "\n---\n".join(formatted_results)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
