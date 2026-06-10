from typing import List, Dict, Optional, Any
from abc import ABC

from backend.store.vector import VectorDatabase, get_vector_db_client, VectorDBType
from backend.v1.app.config.config import settings


class CollectionDAO(ABC):
    """
    集合数据访问层基类
    每个具体的Collection对应一个DAO类，封装该集合的所有操作
    """
    # 子类需要配置对应向量数据库的集合名称
    collection_name: str = None  # Qdrant集合名

    def __init__(self):
        # 获取Qdrant集合名
        if not self.collection_name:
            raise ValueError(f"{self.__class__.__name__} 必须配置collection_name")

        # 获取向量数据库客户端，每个DAO实例对应自己的集合
        self._vector_client = get_vector_db_client(self.collection_name)


    def add_embeddings(self, ids: List[str], embeddings: List[List[float]],
                      metadatas: Optional[List[Dict]] = None,
                      documents: Optional[List[str]] = None) -> None:
        """
        添加向量到当前集合
        :param ids: 向量ID列表
        :param embeddings: 向量数据列表
        :param metadatas: 元数据列表
        :param documents: 文档内容列表
        """
        # 确保所有ID都是字符串类型，兼容整数ID
        str_ids = [str(id) for id in ids]
        self._vector_client.add_embeddings(str_ids, embeddings, metadatas, documents)

    def query_similar(self, query_embeddings: List[List[float]], n_results: int = 10,
                     where: Optional[Dict] = None,
                     where_document: Optional[Dict] = None) -> Dict:
        """
        查询当前集合中的相似向量
        :param query_embeddings: 查询向量列表
        :param n_results: 返回结果数量
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        :return: 查询结果，包含ids、distances、metadatas、documents
        """
        return self._vector_client.query_similar(query_embeddings, n_results, where, where_document)

    def delete_embeddings(self, ids: Optional[List[str]] = None,
                         where: Optional[Dict] = None,
                         where_document: Optional[Dict] = None) -> None:
        """
        从当前集合删除向量
        :param ids: 要删除的向量ID列表
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        """
        # 确保所有ID都是字符串类型，兼容整数ID
        str_ids = [str(id) for id in ids] if ids is not None else None
        self._vector_client.delete_embeddings(str_ids, where, where_document)

    def get_stats(self) -> Dict:
        """
        获取当前集合的统计信息
        :return: 包含count、name、metadata等信息的字典
        """
        return self._vector_client.get_collection_stats()

    def get_collection(self) -> VectorDatabase:
        """
        获取底层的集合操作实例
        :return: 绑定到当前集合的VectorDatabase实例
        """
        return self._vector_client

    def get_all(self, limit: int = 1000, with_vectors: bool = True) -> List[Dict[str, Any]]:
        """
        获取集合中的所有向量数据
        :param limit: 每次批量获取的数量
        :param with_vectors: 是否返回向量数据
        :return: 包含id、vector、content、metadata等信息的列表
        """
        result = self._vector_client.get_all(limit=limit, with_vectors=with_vectors)

        items = []
        for i in range(len(result["ids"])):
            item = {
                "id": result["ids"][i],
                "content": result["documents"][i],
                "metadata": result["metadatas"][i],
            }
            if with_vectors and result["vectors"]:
                item["vector"] = result["vectors"][i]
            items.append(item)

        return items
