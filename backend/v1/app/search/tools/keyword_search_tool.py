from typing import Dict, Any, List, Optional
from .base import BaseSearchTool
from ..core import Query, Document
from ..retrieval import KeywordRetriever
from ..post_processing import Deduplicator, Filter, Merger, Reranker
from ..config import RETRIEVAL_CONFIG, POST_PROCESSING_CONFIG


class KeywordSearchTool(BaseSearchTool):
    """
    关键词检索工具，基于全文索引进行精确匹配检索
    适合查找包含特定关键词、特定信息、列表类、统计类的问题
    """

    @property
    def name(self) -> str:
        return "keyword_search"

    @property
    def description(self) -> str:
        return "通过关键词精确匹配检索知识库中的信息。" \
               "适用于：查找特定信息、列表查询、统计查询、包含特定关键词的文档查找等场景。" \
               "当问题需要精确匹配特定关键词或需要查找列表类信息时使用此工具。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_top_k = RETRIEVAL_CONFIG.get("default_top_k", 10)
        self.max_top_k = 20
        self.min_score_threshold = RETRIEVAL_CONFIG.get("min_score_threshold", 0.6)

        # 初始化检索器
        self.retriever = KeywordRetriever()

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
        """执行关键词检索"""
        query_text = params.get("query", "")
        top_k = min(params.get("top_k", self.default_top_k), self.max_top_k)
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询关键词不能为空"

        try:
            # 构建查询对象，启用关键词扩展
            query = Query(
                text=query_text,
                expanded_keywords=query_text.split()  # 简单分词，实际场景可以用更专业的分词器
            )

            # 执行检索
            documents = self.retriever.retrieve(query, top_k=top_k)

            # 后处理
            if enable_post_processing:
                for processor in self.post_processors:
                    documents = processor.process(documents, query)

            # 过滤低得分结果
            documents = [doc for doc in documents if doc.score >= self.min_score_threshold]

            if not documents:
                return "未找到包含相关关键词的信息"

            # 格式化结果
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

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
