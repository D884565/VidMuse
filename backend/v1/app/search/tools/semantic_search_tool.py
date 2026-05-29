from typing import Dict, Any, List
from .base import BaseSearchTool
from ..core import Query, Document
from ..retrieval import VectorRetriever, ChromaDBRetriever


class SemanticSearchTool(BaseSearchTool):
    """
    语义检索工具，基于向量相似度检索知识库中的相关信息
    适合回答需要专业知识、概念解释、详细说明等类型的问题
    """
    name = "semantic_search"
    description = "在知识库中进行语义相似度检索，查找与查询内容相关的文档信息。" \
                  "适用于：概念解释、原理说明、技术细节查询、文档内容查找、知识问答等场景。" \
                  "当问题需要专业知识或内部文档信息时必须使用此工具。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户的查询问题，需要清晰明确地描述要查询的内容"
            },
            "top_k": {
                "type": "integer",
                "description": "返回的结果数量，默认10，最大不超过20",
                "default": 10,
                "minimum": 1,
                "maximum": 20
            },
            "vector_db": {
                "type": "string",
                "description": "使用的向量数据库类型，可选值：milvus, chromadb，默认milvus",
                "default": "milvus",
                "enum": ["milvus", "chromadb"]
            },
            "enable_post_processing": {
                "type": "boolean",
                "description": "是否启用结果后处理（去重、过滤、重排序等），默认启用",
                "default": True
            }
        },
        "required": ["query"]
    }

    # 语义检索固定使用semantic类型
    default_retrieval_type = "semantic"
    max_top_k = 20

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 语义检索特有的检索器
        self.milvus_retriever = VectorRetriever()
        self.chromadb_retriever = ChromaDBRetriever()

    def retrieve_documents(self, query: Query, top_k: int = 10) -> List[Document]:
        """重写检索方法，支持选择向量数据库"""
        # 语义检索不需要意图识别，直接使用指定的向量数据库
        vector_db = getattr(query, "vector_db", "milvus")
        top_k = min(top_k, self.max_top_k)

        if vector_db == "chromadb":
            retriever = self.chromadb_retriever
        else:
            retriever = self.milvus_retriever

        return retriever.retrieve(query, top_k)

    def execute(self, params: Dict[str, Any]) -> str:
        """执行语义检索（模板实现，具体逻辑后续补充）"""
        query_text = params.get("query", "")
        top_k = params.get("top_k", self.default_top_k)
        vector_db = params.get("vector_db", "milvus")
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 1. 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type="semantic",
                metadata={"vector_db": vector_db}
            )

            # 2. 语义检索不需要复杂的查询增强，可根据需要选择性调用
            # query = self.enhance_query(query)

            # 3. 检索文档（使用重写的检索方法）
            documents = self.retrieve_documents(query, top_k)

            # 4. 结果处理
            if enable_post_processing:
                processed_docs = self.process_results(documents, query)
            else:
                processed_docs = [doc for doc in documents if doc.score >= self.min_score_threshold]

            # 5. 自定义格式化
            return self._format_semantic_results(processed_docs)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"

    def _format_semantic_results(self, documents: List[Document]) -> str:
        """语义检索结果的专用格式化"""
        if not documents:
            return "未找到相关信息"

        formatted_results = []
        for i, doc in enumerate(documents, 1):
            source_info = f"来源: {doc.source_type}"
            if doc.metadata.get("collection"):
                source_info += f", 集合: {doc.metadata['collection']}"

            formatted_results.append(
                f"[{i}] 相关度: {doc.score:.2f}\n"
                f"{source_info}\n"
                f"内容: {doc.content}\n"
            )

        return "语义检索找到以下相关信息：\n\n" + "\n---\n".join(formatted_results)
