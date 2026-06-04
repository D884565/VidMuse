from typing import List, Dict, Optional
from .base import CollectionDAO
from backend.v1.app.config.config import settings


class ImageKnowledgeDAO(CollectionDAO):
    """
    图片知识库集合数据访问层
    存储图片特征向量和相关知识
    """
    chroma_collection_name = settings.CHROMADB_IMAGE_COLLECTION
    milvus_collection_name = settings.MILVUS_IMG_COLLECTION
    qdrant_collection_name = settings.QDRANT_IMAGE_COLLECTION

    def query_by_image_set_id(self, image_set_id: str, query_embeddings: List[List[float]],
                             n_results: int = 10) -> Dict:
        """
        查询指定图片集的相似图片
        :param image_set_id: 图片集ID
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :return: 查询结果
        """
        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"image_set_id": image_set_id}
        )

    def delete_by_image_set_id(self, image_set_id: str) -> None:
        """
        删除指定图片集的所有图片
        :param image_set_id: 图片集ID
        """
        self.delete_embeddings(where={"image_set_id": image_set_id})

    def add_image_knowledge(self, image_ids: List[str], image_set_id: str,
                           embeddings: List[List[float]], descriptions: List[str],
                           image_urls: List[str]) -> None:
        """
        批量添加图片知识
        :param image_ids: 图片ID列表
        :param image_set_id: 所属图片集ID
        :param embeddings: 图片特征向量列表
        :param descriptions: 图片描述列表
        :param image_urls: 图片URL列表
        """
        metadatas = [
            {
                "image_set_id": image_set_id,
                "image_url": image_url,
                "source": "image_knowledge"
            }
            for image_url in image_urls
        ]

        self.add_embeddings(
            ids=image_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=descriptions
        )
