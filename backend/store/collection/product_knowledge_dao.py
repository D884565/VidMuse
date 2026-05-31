from typing import List, Dict, Optional
from .base import CollectionDAO
from backend.v1.app.config.config import settings


class ProductKnowledgeDAO(CollectionDAO):
    """
    产品知识库集合数据访问层
    存储产品相关的结构化知识向量
    """
    chroma_collection_name = settings.MILVUS_PRODUCT_COLLECTION
    milvus_collection_name = settings.MILVUS_PRODUCT_COLLECTION

    def query_by_product_id(self, product_id: str, query_embeddings: List[List[float]],
                           n_results: int = 10) -> Dict:
        """
        查询指定产品的相关知识
        :param product_id: 产品ID
        :param query_embeddings: 查询向量
        :param n_results: 返回结果数量
        :return: 查询结果
        """
        return self.query_similar(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"product_id": product_id}
        )

    def delete_by_product_id(self, product_id: str) -> None:
        """
        删除指定产品的所有知识
        :param product_id: 产品ID
        """
        self.delete_embeddings(where={"product_id": product_id})

    def add_product_knowledge(self, knowledge_ids: List[str], product_id: str,
                             embeddings: List[List[float]], contents: List[str],
                             knowledge_types: List[str] = None) -> None:
        """
        批量添加产品知识
        :param knowledge_ids: 知识ID列表
        :param product_id: 所属产品ID
        :param embeddings: 向量列表
        :param contents: 知识内容列表
        :param knowledge_types: 知识类型列表（可选：FAQ、参数、使用说明等）
        """
        if knowledge_types is None:
            knowledge_types = ["general"] * len(knowledge_ids)

        metadatas = [
            {
                "product_id": product_id,
                "type": knowledge_type,
                "source": "product_knowledge"
            }
            for knowledge_type in knowledge_types
        ]

        self.add_embeddings(
            ids=knowledge_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=contents
        )
