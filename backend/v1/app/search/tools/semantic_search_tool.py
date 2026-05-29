from typing import Dict, Any, List, Optional
from .base import BaseSearchTool
from ..core import Query, Document
from ..retrieval import VectorRetriever, ChromaDBRetriever
from ..post_processing import Deduplicator, Filter, Merger, Reranker
from ..config import RETRIEVAL_CONFIG, POST_PROCESSING_CONFIG


class SemanticSearchTool(BaseSearchTool):
    """
    语义检索工具，基于向量相似度检索知识库中的相关信息
    适合回答需要专业知识、概念解释、详细说明等类型的问题
    """

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return "在知识库中进行语义相似度检索，查找与查询内容相关的文档信息。" \
               "适用于：概念解释、原理说明、技术细节查询、文档内容查找、知识问答等场景。" \
               "当问题需要专业知识或内部文档信息时必须使用此工具。"

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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.max_top_k = 20
        self.min_score_threshold = RETRIEVAL_CONFIG.get("min_score_threshold", 0.6)

        # 初始化检索器
        self.milvus_retriever = VectorRetriever()
        self.chromadb_retriever = ChromaDBRetriever()

        # 初始化后处理器
        self.post_processors = self._init_post_processors()

    def _init_post_processors(self) -> List[Any]:
        """初始化后处理器"""
        processors = []
        config = POST_PROCESSING_CONFIG

        if config.get("enable_deduplication", True):
            processors.append(Deduplicator())
        if config.get("enable_filtering", True):
            processors.append(Filter())
        if config.get("enable_merging", True):
            processors.append(Merger())
        if config.get("enable_reranking", True):
            processors.append(Reranker())

        return processors

    def execute(self, params: Dict[str, Any]) -> str:
        """执行语义检索"""
        query_text = params.get("query", "")
        top_k = min(params.get("top_k", self.default_top_k), self.max_top_k)
        vector_db = params.get("vector_db", "milvus")
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 选择检索器
            if vector_db == "chromadb":
                retriever = self.chromadb_retriever
            else:
                retriever = self.milvus_retriever

            # 构建查询对象
            query = Query(text=query_text)

            # 执行检索
            documents = retriever.retrieve(query, top_k=top_k)

            # 后处理
            if enable_post_processing:
                for processor in self.post_processors:
                    documents = processor.process(documents, query)

            # 过滤低得分结果
            documents = [doc for doc in documents if doc.score >= self.min_score_threshold]

            if not documents:
                return "未找到相关信息"

            # 格式化结果
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

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
