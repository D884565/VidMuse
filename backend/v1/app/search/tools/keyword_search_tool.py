from typing import Dict, Any, List
from .base import BaseSearchTool
from ..core import Query, Document
from ..retrieval import KeywordRetriever


class KeywordSearchTool(BaseSearchTool):
    """
    关键词检索工具，基于全文索引进行精确匹配检索
    适合查找包含特定关键词、特定信息、列表类、统计类的问题
    """
    name = "keyword_search"
    description = "通过关键词精确匹配检索知识库中的信息。" \
                  "适用于：查找特定信息、列表查询、统计查询、包含特定关键词的文档查找等场景。" \
                  "当问题需要精确匹配特定关键词或需要查找列表类信息时使用此工具。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户的查询关键词，多个关键词用空格分隔"
            },
            "top_k": {
                "type": "integer",
                "description": "返回的结果数量，默认10，最大不超过20",
                "default": 10,
                "minimum": 1,
                "maximum": 20
            },
            "enable_post_processing": {
                "type": "boolean",
                "description": "是否启用结果后处理（去重、过滤、重排序等），默认启用",
                "default": True
            }
        },
        "required": ["query"]
    }

    # 关键词检索固定使用keyword类型
    default_retrieval_type = "keyword"
    max_top_k = 20

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 关键词检索特有的检索器
        self.keyword_retriever = KeywordRetriever()

    def retrieve_documents(self, query: Query, top_k: int = 10) -> List[Document]:
        """重写检索方法，使用关键词检索器"""
        top_k = min(top_k, self.max_top_k)
        # 关键词扩展
        query.expanded_keywords = query.text.split()  # 简单分词，后续可替换为专业分词器
        return self.keyword_retriever.retrieve(query, top_k)

    def execute(self, params: Dict[str, Any]) -> str:
        """执行关键词检索（模板实现，具体逻辑后续补充）"""
        query_text = params.get("query", "")
        top_k = params.get("top_k", self.default_top_k)
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询关键词不能为空"

        try:
            # 1. 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type="keyword"
            )

            # 2. 关键词检索不需要复杂的查询增强
            # query = self.enhance_query(query)

            # 3. 检索文档
            documents = self.retrieve_documents(query, top_k)

            # 4. 结果处理
            if enable_post_processing:
                processed_docs = self.process_results(documents, query)
            else:
                processed_docs = [doc for doc in documents if doc.score >= self.min_score_threshold]

            # 5. 自定义格式化
            return self._format_keyword_results(processed_docs)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"

    def _format_keyword_results(self, documents: List[Document]) -> str:
        """关键词检索结果的专用格式化"""
        if not documents:
            return "未找到包含相关关键词的信息"

        formatted_results = []
        for i, doc in enumerate(documents, 1):
            source_info = f"来源: {doc.source_type}"
            if doc.metadata.get("index"):
                source_info += f", 索引: {doc.metadata['index']}"
            if doc.metadata.get("matched_keywords"):
                source_info += f", 匹配关键词: {', '.join(doc.metadata['matched_keywords'])}"

            formatted_results.append(
                f"[{i}] 相关度: {doc.score:.2f}\n"
                f"{source_info}\n"
                f"内容: {doc.content}\n"
            )

        return "关键词检索找到以下相关信息：\n\n" + "\n---\n".join(formatted_results)
