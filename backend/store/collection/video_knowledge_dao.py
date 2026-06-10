from typing import List, Dict, Optional
import logging
from .base import CollectionDAO
from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)


class VideoKnowledgeDAO(CollectionDAO):
    """
    视频知识库集合数据访问层
    存储视频整体信息和结构化知识向量
    """
    collection_name = settings.QDRANT_VIDEO_COLLECTION

    def query_by_video_id(self, video_id: str, query_embeddings: List[List[float]],
                         n_results: int = 10) -> Dict:
        """
        查询指定视频的相关知识
        :param video_id: 视频ID
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :return: 查询结果
        """
        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"video_id": video_id}
        )

    def delete_by_video_id(self, video_id: str) -> None:
        """
        删除指定视频的所有知识
        :param video_id: 视频ID
        """
        self.delete_embeddings(where={"video_id": video_id})

    def get_video_embedding(self, video_id: str) -> Optional[List[float]]:
        """
        获取指定视频的整体向量
        :param video_id: 视频ID
        :return: 向量列表，如果不存在则返回None
        """
        try:
            from qdrant_client import models
            results, _ = self._vector_client.client.scroll(
                collection_name=self._vector_client.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="video_id",
                            match=models.MatchValue(value=video_id)
                        )
                    ]
                ),
                limit=1,
                with_vectors=True,
                with_payload=False
            )
            if results and len(results) > 0:
                return results[0].vector
        except Exception as e:
            logger.error(f"从Qdrant获取视频向量失败: {str(e)}")

        return None

    def query_by_category(self, category: str, query_embeddings: List[List[float]],
                         n_results: int = 10) -> Dict:
        """
        查询指定分类的视频知识
        :param category: 视频分类
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :return: 查询结果
        """
        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"category": category}
        )

    def add_video_knowledge(self, knowledge_ids: List[str], video_id: str,
                           embeddings: List[List[float]], contents: List[str],
                           titles: List[str] = None, categories: List[str] = None,
                           tags: List[List[str]] = None) -> None:
        """
        批量添加视频知识
        :param knowledge_ids: 知识ID列表
        :param video_id: 所属视频ID
        :param embeddings: 向量列表
        :param contents: 知识内容列表
        :param titles: 视频标题列表（可选）
        :param categories: 视频分类列表（可选）
        :param tags: 视频标签列表（可选）
        """
        if titles is None:
            titles = [""] * len(knowledge_ids)
        if categories is None:
            categories = ["general"] * len(knowledge_ids)
        if tags is None:
            tags = [[]] * len(knowledge_ids)

        metadatas = []
        for i in range(len(knowledge_ids)):
            metadata = {
                "video_id": video_id,
                "title": titles[i],
                "category": categories[i],
                "tags": ",".join(tags[i]) if isinstance(tags[i], list) else str(tags[i]),
                "source": "video_knowledge"
            }
            metadatas.append(metadata)

        self.add_embeddings(
            ids=knowledge_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=contents
        )
