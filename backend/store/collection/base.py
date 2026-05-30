from typing import List, Dict, Optional
from abc import ABC

from backend.store.vector import VectorDatabase, get_vector_db_client, VectorDBType, ChromaDBClient
from backend.v1.app.config.config import settings


class CollectionDAO(ABC):
    """
    集合数据访问层基类
    每个具体的Collection对应一个DAO类，封装该集合的所有操作
    """
    # 子类需要配置对应向量数据库的集合名称
    chroma_collection_name: str = None  # ChromaDB集合名
    milvus_collection_name: str = None  # Milvus集合名

    _vector_client: VectorDatabase = None

    def __init__(self):
        # 根据当前配置的向量数据库类型获取对应的集合名
        if settings.VECTOR_DB_TYPE == VectorDBType.CHROMADB:
            if not self.chroma_collection_name:
                raise ValueError(f"{self.__class__.__name__} 必须配置chroma_collection_name")
            self.collection_name = self.chroma_collection_name
        elif settings.VECTOR_DB_TYPE == VectorDBType.MILVUS:
            if not self.milvus_collection_name:
                raise ValueError(f"{self.__class__.__name__} 必须配置milvus_collection_name")
            self.collection_name = self.milvus_collection_name
        else:
            raise ValueError(f"不支持的向量数据库类型: {settings.VECTOR_DB_TYPE}")

        # 获取向量数据库客户端（单例）
        if CollectionDAO._vector_client is None:
            CollectionDAO._vector_client = get_vector_db_client(self.collection_name)


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
