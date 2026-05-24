from typing import List, Dict, Any, Optional, Union
import json

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import (
    EmbeddingRequest,
    MultimodalContent,
    ChatRequest,
    ChatMessage,
    TextContent,
    ImageUrlContent,
    VideoUrlContent
)
from backend.store.vector.chromadb_client import get_chromadb_client
from backend.framework.exceptions.exceptions import BaseAppException
from backend.framework.exceptions.error_codes import PARAM_ERROR


def search(
    query: Union[str, MultimodalContent, List[MultimodalContent]],
    top_k: int = 10,
    where: Optional[Dict[str, Any]] = None,
    rerank: bool = True,
    embedding_model: Optional[str] = None,
    rerank_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    RAG搜索核心方法：多模态嵌入 -> 向量检索 -> 大模型重排序

    :param query: 查询内容，支持纯文本字符串或多模态内容对象（文本、图片、视频）
    :param top_k: 返回的最相关结果数量，默认10
    :param where: 向量检索的过滤条件，可选
    :param rerank: 是否启用大模型重排序，默认True
    :param embedding_model: 嵌入模型名称，不指定则使用默认模型
    :param rerank_model: 重排序模型名称，不指定则使用默认模型
    :return: 搜索结果，包含检索到的文档、元数据、相似度分数等
    """
    # 参数验证
    if top_k < 1 or top_k > 100:
        raise BaseAppException(PARAM_ERROR, message="top_k必须在1-100之间")

    # 标准化查询内容格式
    if isinstance(query, str):
        # 纯文本查询
        query_contents = [TextContent(text=query)]
    elif isinstance(query, (TextContent, ImageUrlContent, VideoUrlContent)):
        # 单个多模态对象
        query_contents = [query]
    elif isinstance(query, list) and all(isinstance(item, (TextContent, ImageUrlContent, VideoUrlContent)) for item in query):
        # 多模态对象列表
        query_contents = query
    else:
        raise BaseAppException(PARAM_ERROR, message="不支持的查询内容格式")

    # 1. 生成查询向量
    llm = VolcanoLLM(key=None, model_name=None)

    embedding_request = EmbeddingRequest(
        texts=query_contents,
        model=embedding_model
    )
    embedding_response = llm.embedding(embedding_request)
    query_embeddings = embedding_response.embeddings

    # 2. 向量检索
    chromadb_client = get_chromadb_client()
    search_results = chromadb_client.query_similar(
        query_embeddings=query_embeddings,
        n_results=top_k * 2 if rerank else top_k,  # 重排序时多召回一些结果
        where=where
    )

    # 处理检索结果
    documents = search_results.get("documents", [[]])[0] if search_results.get("documents") else []
    metadatas = search_results.get("metadatas", [[]])[0] if search_results.get("metadatas") else []
    distances = search_results.get("distances", [[]])[0] if search_results.get("distances") else []
    ids = search_results.get("ids", [[]])[0] if search_results.get("ids") else []

    # 如果没有结果或者不需要重排序，直接返回
    if not documents or not rerank:
        return {
            "query": query,
            "results": [
                {
                    "id": id_,
                    "document": doc,
                    "metadata": meta,
                    "score": 1 - dist if dist is not None else None  # 转换为相似度分数，越大越相似
                }
                for id_, doc, meta, dist in zip(ids, documents, metadatas, distances)
            ][:top_k],
            "embedding_usage": embedding_response.usage.dict(),
            "rerank_enabled": rerank,
            "rerank_usage": None
        }

    # 3. 大模型重排序
    # 构建重排序prompt
    rerank_prompt = _build_rerank_prompt(query_contents, documents, metadatas)

    chat_request = ChatRequest(
        messages=[
            ChatMessage(role="system", content="你是一个专业的内容排序助手，需要根据用户查询和候选内容的相关性进行排序。"),
            ChatMessage(role="user", content=rerank_prompt)
        ],
        model=rerank_model,
        temperature=0.1,  # 低温度保证排序一致性
        max_tokens=1024
    )

    rerank_response = llm.chat(chat_request)

    # 解析重排序结果
    reranked_indices = _parse_rerank_response(rerank_response.content, len(documents))

    # 根据重排序结果重新组织返回数据
    reranked_results = []
    for idx in reranked_indices[:top_k]:
        if 0 <= idx < len(documents):
            reranked_results.append({
                "id": ids[idx],
                "document": documents[idx],
                "metadata": metadatas[idx],
                "score": 1 - distances[idx] if distances[idx] is not None else None,
                "rerank_rank": reranked_indices.index(idx) + 1  # 重排序排名，从1开始
            })

    return {
        "query": query,
        "results": reranked_results,
        "embedding_usage": embedding_response.usage.dict(),
        "rerank_enabled": True,
        "rerank_usage": rerank_response.usage.dict()
    }


def _build_rerank_prompt(
    query_contents: List[MultimodalContent],
    documents: List[str],
    metadatas: List[Dict[str, Any]]
) -> str:
    """
    构建重排序的提示词

    :param query_contents: 查询内容列表
    :param documents: 检索到的文档列表
    :param metadatas: 文档元数据列表
    :return: 构建好的提示词
    """
    # 提取查询文本
    query_text = ""
    for content in query_contents:
        if isinstance(content, TextContent):
            query_text += content.text + " "
        elif isinstance(content, ImageUrlContent):
            query_text += "[图片内容] "
        elif isinstance(content, VideoUrlContent):
            query_text += "[视频内容] "

    # 构建候选内容列表
    candidates_text = ""
    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        meta_str = ", ".join([f"{k}: {v}" for k, v in meta.items()]) if meta else "无"
        candidates_text += f"候选{i+1}:\n内容: {doc}\n元数据: {meta_str}\n\n"

    prompt = f"""请根据用户查询内容，对以下候选内容按照相关性从高到低进行排序，只需要返回候选编号的列表，不需要其他解释。

用户查询: {query_text.strip()}

候选内容:
{candidates_text}

返回格式示例：[3, 1, 2, 4, ...]
"""

    return prompt


def _parse_rerank_response(response_content: str, total_candidates: int) -> List[int]:
    """
    解析重排序的响应结果

    :param response_content: 大模型返回的响应内容
    :param total_candidates: 候选内容总数
    :return: 排序后的候选索引列表（从0开始）
    """
    try:
        # 尝试解析JSON格式的列表
        content = response_content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        # 提取数字列表
        import re
        numbers = re.findall(r'\d+', content)
        indices = [int(num) - 1 for num in numbers if num.isdigit()]  # 转换为从0开始的索引

        # 去重并过滤无效索引
        seen = set()
        unique_indices = []
        for idx in indices:
            if 0 <= idx < total_candidates and idx not in seen:
                unique_indices.append(idx)
                seen.add(idx)

        # 补充缺失的索引
        for idx in range(total_candidates):
            if idx not in seen:
                unique_indices.append(idx)

        return unique_indices

    except Exception:
        # 如果解析失败，返回原始顺序
        return list(range(total_candidates))
