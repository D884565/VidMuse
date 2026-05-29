from typing import Dict, Any, List, Optional
from .base import BaseSearchTool
from ..core import Query, Document
from ..retrieval import HybridRetriever
from ..post_processing import Deduplicator, Filter, Merger, Reranker
from ..config import RETRIEVAL_CONFIG, POST_PROCESSING_CONFIG


class HybridSearchTool(BaseSearchTool):
    """
    混合检索工具，结合语义检索和关键词检索的优势
    适合复杂查询，需要同时考虑语义相似度和关键词匹配的场景
    """

    @property
    def name(self) -> str:
        return "hybrid_search"

    @property
    def description(self) -> str:
        return "结合语义检索和关键词检索的混合检索，同时利用向量相似度和关键词匹配。" \
               "适用于：复杂查询、多关键词查询、需要同时考虑语义和精确匹配的场景。" \
               "当查询比较复杂，单独使用语义或关键词检索效果不好时使用此工具。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户的查询问题"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的结果数量，默认10，最大不超过20",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20
                },
                "vector_weight": {
                    "type": "number",
                    "description": "语义检索结果的权重，0-1之间，默认0.6",
                    "default": 0.6,
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "keyword_weight": {
                    "type": "number",
                    "description": "关键词检索结果的权重，0-1之间，默认0.4",
                    "default": 0.4,
                    "minimum": 0.0,
                    "maximum": 1.0
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

    def execute(self, params: Dict[str, Any]) -> str:
        """执行混合检索"""
        query_text = params.get("query", "")
        top_k = min(params.get("top_k", self.default_top_k), self.max_top_k)
        vector_weight = params.get("vector_weight", 0.6)
        keyword_weight = params.get("keyword_weight", 0.4)
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 构建自定义配置的混合检索器
            hybrid_config = {
                "hybrid_vector_weight": vector_weight,
                "hybrid_keyword_weight": keyword_weight
            }
            retriever = HybridRetriever(config=hybrid_config)

            # 构建查询对象
            query = Query(text=query_text)

            # 执行检索
            documents = retriever.retrieve(query, top_k=top_k)

            # 后处理
            if enable_post_processing:
                # 初始化后处理器
                post_processors = []
                config = POST_PROCESSING_CONFIG
                if config.get("enable_deduplication", True):
                    post_processors.append(Deduplicator())
                if config.get("enable_filtering", True):
                    post_processors.append(Filter())
                if config.get("enable_merging", True):
                    post_processors.append(Merger())
                if config.get("enable_reranking", True):
                    post_processors.append(Reranker())

                for processor in post_processors:
                    documents = processor.process(documents, query)

            # 过滤低得分结果
            documents = [doc for doc in documents if doc.score >= self.min_score_threshold]

            if not documents:
                return "未找到相关信息"

            # 格式化结果
            formatted_results = []
            for i, doc in enumerate(documents, 1):
                source_info = f"来源: {doc.source_type}"
                if doc.metadata.get("original_score"):
                    source_info += f", 原始得分: {doc.metadata['original_score']:.2f}"
                if doc.metadata.get("weight"):
                    source_info += f", 权重: {doc.metadata['weight']:.2f}"

                formatted_results.append(
                    f"[{i}] 综合得分: {doc.score:.2f}\n"
                    f"{source_info}\n"
                    f"内容: {doc.content}\n"
                )

            return "混合检索找到以下相关信息：\n\n" + "\n---\n".join(formatted_results)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"
