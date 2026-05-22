import chromadb
import load_dotenv
from chromadb import Settings
from chromadb.config import Settings as ChromaSettings

from backend.vidmuse.config.settings import settings




class ChromaDBClient:
    """ChromaDB 向量数据库客户端封装"""
    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化客户端（仅执行一次）"""
        if self._initialized:
            return
        # 初始化ChromaDB客户端
        self.client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT,
            settings=Settings(anonymized_telemetry=False)
        )
        # 获取或创建集合
        self.collection = self._ensure_collection_exists()
        self._initialized = True

    def _ensure_collection_exists(self):
        """确保集合存在，不存在则创建"""
        try:
            collection = self.client.get_collection(name=settings.CHROMADB_COLLECTION)
        except Exception:
            # 集合不存在，创建新集合
            collection = self.client.create_collection(
                name=settings.CHROMADB_COLLECTION,
                metadata={"description": "视频内容向量存储集合"},
            )
        return collection

    def add_embeddings(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict] = None, documents: list[str] = None):
        """
        添加向量到集合
        :param ids: 唯一ID列表
        :param embeddings: 向量列表
        :param metadatas: 元数据列表
        :param documents: 原始文档列表
        """
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
        except Exception as e:
            raise RuntimeError(f"添加向量到ChromaDB失败: {str(e)}")

    def query_similar(self, query_embeddings: list[list[float]], n_results: int = 10, where: dict = None, where_document: dict = None):
        """
        查询相似向量
        :param query_embeddings: 查询向量列表
        :param n_results: 返回结果数量
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        :return: 查询结果
        """
        try:
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            return results
        except Exception as e:
            raise RuntimeError(f"查询ChromaDB相似向量失败: {str(e)}")

    def delete_embeddings(self, ids: list[str] = None, where: dict = None, where_document: dict = None):
        """
        删除向量
        :param ids: 要删除的ID列表
        :param where: 元数据过滤条件
        :param where_document: 文档内容过滤条件
        """
        try:
            self.collection.delete(
                ids=ids,
                where=where,
                where_document=where_document
            )
        except Exception as e:
            raise RuntimeError(f"删除ChromaDB向量失败: {str(e)}")

    def get_collection_stats(self):
        """获取集合统计信息"""
        try:
            return {
                "count": self.collection.count(),
                "name": self.collection.name,
                "metadata": self.collection.metadata
            }
        except Exception as e:
            raise RuntimeError(f"获取ChromaDB集合统计失败: {str(e)}")


# 全局ChromaDB客户端实例（懒加载）
def get_chromadb_client():
    """获取ChromaDB客户端实例"""
    return ChromaDBClient()
