"""RAG 服务适配器：对接真实向量知识库，为剧本生成提供检索能力。"""
import asyncio
import logging
from typing import List, Optional

from .core import Document

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import EmbeddingRequest, TextContent, ImageUrlContent
from backend.store.collection import (
    VideoKnowledgeDAO,
    SliceKnowledgeDAO,
    ImageKnowledgeDAO,
    ProductKnowledgeDAO,
)

logger = logging.getLogger(__name__)


class RAGServiceAdapter:
    """适配 ScriptGenerationService._retrieve_references() 所需的 rag_service 接口。

    直接对接 store/collection/ 层的真实 DAO，通过 Volcano embedding 做向量检索。
    """

    def __init__(self):
        self._llm = None
        self._video_dao = None
        self._slice_dao = None
        self._image_dao = None
        self._product_dao = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    @property
    def video_dao(self):
        if self._video_dao is None:
            self._video_dao = VideoKnowledgeDAO()
        return self._video_dao

    @property
    def slice_dao(self):
        if self._slice_dao is None:
            self._slice_dao = SliceKnowledgeDAO()
        return self._slice_dao

    @property
    def image_dao(self):
        if self._image_dao is None:
            self._image_dao = ImageKnowledgeDAO()
        return self._image_dao

    @property
    def product_dao(self):
        if self._product_dao is None:
            self._product_dao = ProductKnowledgeDAO()
        return self._product_dao

    # ---------- 公开接口（async，供 ScriptGenerationService 调用） ----------

    async def search_scripts(self, query: str, top_k: int = 10) -> List[Document]:
        """检索参考剧本：从视频知识库 + 片段知识库中检索。"""
        return await self._run(self._search_scripts, query, top_k)

    async def search_assets(self, query: str, image_url: str = None, top_k: int = 10, image_urls: list[str] = None) -> List[Document]:
        """检索参考视觉素材：从图片知识库中检索，支持多张参考图做多模态查询。"""
        urls = image_urls or ([image_url] if image_url else [])
        return await self._run(self._search_assets, query, top_k, urls)

    async def search_product_knowledge(self, query: str, top_k: int = 10) -> List[Document]:
        """检索商品知识：从产品知识库中检索。"""
        return await self._run(self._search_product, query, top_k)

    # ---------- 内部实现（同步，在线程池中运行） ----------

    def _embed_query(self, text: str) -> List[float]:
        """将查询文本转为向量。"""
        response = self.llm.embedding(EmbeddingRequest(
            texts=[TextContent(text=text)],
        ))
        if not response.embeddings:
            raise ValueError("embedding 返回空结果")
        return response.embeddings[0]

    def _embed_images(self, image_urls: list[str]) -> List[float]:
        """将多张图片转为向量（取平均）。"""
        contents = [ImageUrlContent(image_url={"url": url}) for url in image_urls]
        response = self.llm.embedding(EmbeddingRequest(texts=contents))
        if not response.embeddings:
            raise ValueError("image embedding 返回空结果")
        # 多张图取平均向量
        return self._average_vectors(response.embeddings)

    @staticmethod
    def _average_vectors(vectors: list[list[float]]) -> list[float]:
        """对多个向量取平均。"""
        if len(vectors) == 1:
            return vectors[0]
        dim = len(vectors[0])
        result = [0.0] * dim
        for v in vectors:
            for i in range(dim):
                result[i] += v[i]
        n = len(vectors)
        return [x / n for x in result]

    @staticmethod
    def _merge_vectors(text_vec: list[float], image_vec: list[float], text_weight: float = 0.6) -> list[float]:
        """融合文本向量和图片向量（加权平均）。"""
        img_weight = 1.0 - text_weight
        return [t * text_weight + i * img_weight for t, i in zip(text_vec, image_vec)]

    def _query_dao(self, dao, query_vector: List[float], top_k: int) -> List[Document]:
        """通用 DAO 查询 + 结果转换。"""
        result = dao.query_similar(
            query_embeddings=[query_vector],
            n_results=top_k,
        )
        return self._to_documents(result)

    def _search_scripts(self, query_text: str, top_k: int) -> List[Document]:
        """从视频知识库和片段知识库并行检索剧本参考。"""
        query_vector = self._embed_query(query_text)

        video_docs = self._query_dao(self.video_dao, query_vector, top_k)
        slice_docs = self._query_dao(self.slice_dao, query_vector, top_k)

        # 合并去重，按相似度排序
        all_docs = video_docs + slice_docs
        all_docs.sort(key=lambda d: d.score, reverse=True)
        return all_docs[:top_k]

    def _search_assets(self, query_text: str, top_k: int, image_urls: list[str] = None) -> List[Document]:
        """从图片知识库检索视觉素材，支持多模态 embedding（文本 + 参考图）。"""
        query_vector = self._embed_query(query_text)

        # 如果有参考图，用多模态 embedding 融合文本和图片向量
        if image_urls:
            try:
                image_vector = self._embed_images(image_urls[:3])  # 最多取3张
                query_vector = self._merge_vectors(query_vector, image_vector)
            except Exception as e:
                logger.warning(f"[RAGAdapter] 参考图 embedding 失败，降级为纯文本查询: {e}")

        return self._query_dao(self.image_dao, query_vector, top_k)

    def _search_product(self, query_text: str, top_k: int) -> List[Document]:
        """从产品知识库检索商品知识。"""
        query_vector = self._embed_query(query_text)
        return self._query_dao(self.product_dao, query_vector, top_k)

    @staticmethod
    def _to_documents(query_result: dict) -> List[Document]:
        """将 ChromaDB/Milvus 查询结果转换为 List[Document]。"""
        if not query_result or not query_result.get("ids"):
            return []

        ids = query_result["ids"][0] if query_result["ids"] else []
        distances = query_result.get("distances", [[]])[0] if query_result.get("distances") else []
        metadatas = query_result.get("metadatas", [[]])[0] if query_result.get("metadatas") else []
        documents = query_result.get("documents", [[]])[0] if query_result.get("documents") else []

        result = []
        for i in range(len(ids)):
            distance = distances[i] if i < len(distances) else 1.0
            metadata = metadatas[i] if i < len(metadatas) else {}
            content = documents[i] if i < len(documents) else ""

            doc = Document(
                id=str(ids[i]),
                content=content or "",
                score=1.0 / (1.0 + distance),
                source="vector",
                source_type=metadata.get("source", "chromadb"),
                title=metadata.get("title"),
                url=metadata.get("image_url"),  # 图片知识库的 URL 存在 metadata["image_url"]
                metadata=metadata,
            )
            result.append(doc)

        return result

    @staticmethod
    async def _run(fn, *args) -> List[Document]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, fn, *args)
        except Exception as e:
            logger.warning(f"[RAGAdapter] 检索异常: {e}")
            return []
