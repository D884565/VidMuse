from typing import Dict, Any
from .base import BaseSearchTool
from ..core import Query, SearchContext


class GeneralSearchTool(BaseSearchTool):
    """
    通用检索工具，使用完整的RAG检索流程
    包含问题增强、意图识别、自动选择检索方式、结果后处理等完整流程
    适合普通的问答场景，不需要手动选择检索方式
    """
    name = "general_search"
    description = "通用智能检索，自动识别查询意图，选择最合适的检索方式。" \
                  "包含完整的问题增强、检索、后处理流程。" \
                  "适用于大多数普通问答场景，不需要手动指定检索方式。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户的查询问题"
            },
            "top_k": {
                "type": "integer",
                "description": "返回的结果数量，默认10",
                "default": 10
            },
            "retrieval_type": {
                "type": "string",
                "description": "强制指定检索类型，可选值：semantic, keyword, hybrid, sql, api，不指定则自动识别",
                "enum": ["semantic", "keyword", "hybrid", "sql", "api"]
            }
        },
        "required": ["query"]
    }

    # 默认检索类型，由意图识别自动决定
    default_retrieval_type = "semantic"

    def execute(self, params: Dict[str, Any]) -> str:
        """执行通用检索（模板实现，具体逻辑后续补充）"""
        query_text = params.get("query", "")
        top_k = params.get("top_k", self.default_top_k)
        retrieval_type = params.get("retrieval_type")

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 1. 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type=retrieval_type,
                required_sources=[]
            )

            # 2. 查询增强（复用基类逻辑）
            query = self.enhance_query(query, SearchContext())

            # 3. 检索文档（复用基类逻辑）
            documents = self.retrieve_documents(query, top_k)

            # 4. 结果处理（复用基类逻辑）
            processed_docs = self.process_results(documents, query)

            # 5. 格式化结果（复用基类逻辑）
            return self.format_results(processed_docs)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
