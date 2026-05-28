from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class VectorDatabase(ABC):
    """向量数据库抽象基类"""

    @abstractmethod
    def add_embeddings(self, ids: List[str], embeddings: List[List[float]],
                      metadatas: Optional[List[Dict]] = None,
                      documents: Optional[List[str]] = None) -> None:
        """
        添加向量到数据库
        :param ids: 向量ID列表
        :param embeddings: 向量数据列表
        :param metadatas: 元数据列表
        :param documents: 文档内容列表
        """
        pass

    @abstractmethod
    def query_similar(self, query_embeddings: List[List[float]], n_results: int = 10,
                     where: Optional[Dict] = None,
                     where_document: Optional[Dict] = None) -> Dict:
        """
        查询相似向量
        :param query_embeddings: 查询向量列表
        :param n_results: 返回结果数量
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        :return: 查询结果，包含ids、distances、metadatas、documents
        """
        pass

    @abstractmethod
    def delete_embeddings(self, ids: Optional[List[str]] = None,
                         where: Optional[Dict] = None,
                         where_document: Optional[Dict] = None) -> None:
        """
        删除向量
        :param ids: 要删除的向量ID列表
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        """
        pass

    @abstractmethod
    def get_collection_stats(self) -> Dict:
        """
        获取集合统计信息
        :return: 包含count、name、metadata等信息的字典
        """
        pass

    @abstractmethod
    def create_index(self, field_name: str, index_type: str, params: Dict) -> None:
        """
        创建索引（Milvus特有方法）
        :param field_name: 字段名
        :param index_type: 索引类型
        :param params: 索引参数
        """
        pass

    @abstractmethod
    def load_collection(self) -> None:
        """加载集合到内存（Milvus特有方法）"""
        pass

    @abstractmethod
    def release_collection(self) -> None:
        """释放集合内存（Milvus特有方法）"""
        pass
