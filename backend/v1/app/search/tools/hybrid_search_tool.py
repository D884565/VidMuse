from typing import Dict, Any, List
from .base import BaseSearchTool
from ..core import Query, Document


class HybridSearchTool(BaseSearchTool):
    """
    混合检索工具，结合语义检索和关键词检索的优势
    适合复杂查询，需要同时考虑语义相似度和关键词匹配的场景
    """
    name = "hybrid_search"
    description = "结合语义检索和关键词检索的混合检索，同时利用向量相似度和关键词匹配。" \
                  "适用于：复杂查询、多关键词查询、需要同时考虑语义和精确匹配的场景。" \
                  "当查询比较复杂，单独使用语义或关键词检索效果不好时使用此工具。"
    parameters_schema = {
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

    # 混合检索使用完整的查询增强流程
    query_enhancer_config = [
        "context",
        "intent",
        "rewrite",
        "expander"
    ]

    # 混合检索只需要混合检索器，支持权重配置
    retriever_config = {
        "hybrid": ("hybrid", {})  # 配置会动态设置权重
    }

    # 混合检索使用完整的后处理流程
    post_processor_config = [
        "deduplicator",
        "filter",
        "merger",
        "reranker"
    ]

    # 混合检索固定使用hybrid类型
    default_retrieval_type = "hybrid"
    max_top_k = 20

    def retrieve_documents(self, query: Query, top_k: int = 10) -> List[Document]:
        """重写检索方法，支持自定义权重的混合检索"""
        top_k = min(top_k, self.max_top_k)
        # 从查询metadata中获取权重配置
        vector_weight = query.metadata.get("vector_weight", 0.6)
        keyword_weight = query.metadata.get("keyword_weight", 0.4)

        # 动态创建带自定义权重的混合检索器
        hybrid_config = {
            "hybrid_vector_weight": vector_weight,
            "hybrid_keyword_weight": keyword_weight
        }
        # 从注册中心获取配置好的混合检索器
        retriever = component_registry.get_retriever("hybrid", hybrid_config)
        return retriever.retrieve(query, top_k)

    def execute(self, params: Dict[str, Any]) -> str:
        """执行混合检索（模板实现，具体逻辑后续补充）"""
        query_text = params.get("query", "")
        top_k = params.get("top_k", self.default_top_k)
        vector_weight = params.get("vector_weight", 0.6)
        keyword_weight = params.get("keyword_weight", 0.4)
        enable_post_processing = params.get("enable_post_processing", True)

        if not query_text:
            return "错误：查询内容不能为空"

        try:
            # 1. 创建查询对象
            query = Query(
                text=query_text,
                retrieval_type="hybrid",
                metadata={
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight
                }
            )

            # 2. 查询增强
            query = self.enhance_query(query)

            # 3. 检索文档
            documents = self.retrieve_documents(query, top_k)

            # 4. 结果处理
            if enable_post_processing:
                processed_docs = self.process_results(documents, query)
            else:
                processed_docs = [doc for doc in documents if doc.score >= self.min_score_threshold]

            # 5. 自定义格式化
            return self._format_hybrid_results(processed_docs)

        except Exception as e:
            return f"检索过程中发生错误：{str(e)}"

    def _format_hybrid_results(self, documents: List[Document]) -> str:
        """混合检索结果的专用格式化"""
        if not documents:
            return "未找到相关信息"

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
