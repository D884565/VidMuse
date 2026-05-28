from typing import List, Dict, Optional
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema, connections

from backend.v1.app.config.config import settings
from .base import VectorDatabase


class MilvusClientWrapper(VectorDatabase):
    """Milvus 向量数据库客户端封装"""
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

        # 连接Milvus服务
        try:
            self.client = MilvusClient(
                uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
                user=settings.MILVUS_USERNAME,
                password=settings.MILVUS_PASSWORD
            )
        except Exception as e:
            raise RuntimeError(f"连接Milvus失败: {str(e)}")

        self.collection_name = settings.MILVUS_COLLECTION
        self.vector_dimension = settings.MILVUS_VECTOR_DIMENSION

        # 确保集合存在
        self.collection = self._ensure_collection_exists()

        # 加载集合到内存
        self.load_collection()

        self._initialized = True

    def _ensure_collection_exists(self):
        """确保集合存在，不存在则创建"""
        if self.client.has_collection(self.collection_name):
            return self.client.get_collection(self.collection_name)

        # 定义集合schema,可以存图像和文本维度的向量
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="document_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dimension),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="document", dtype=DataType.VARCHAR, max_length=65535)
        ]

        schema = CollectionSchema(
            fields=fields,
            description="视频内容向量存储集合",
            enable_dynamic_field=False
        )

        # 创建集合
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                consistency_level="Strong"
            )

            # 创建默认IVF_FLAT索引
            self.create_index(
                field_name="embedding",
                index_type="IVF_FLAT",
                params={"nlist": 1024}
            )

            return self.client.get_collection(self.collection_name)
        except Exception as e:
            raise RuntimeError(f"创建Milvus集合失败: {str(e)}")

    def add_embeddings(self, ids: List[str], embeddings: List[List[float]],
                      metadatas: Optional[List[Dict]] = None,
                      documents: Optional[List[str]] = None) -> None:
        """添加向量到集合"""
        try:
            # 构造插入数据
            data = []
            for i in range(len(ids)):
                item = {
                    "id": ids[i],
                    "document_embedding": embeddings[i],
                    "metadata": metadatas[i] if metadatas else {},
                    "document": documents[i] if documents else ""
                }
                data.append(item)

            # 插入数据
            self.client.insert(
                collection_name=self.collection_name,
                data=data
            )
        except Exception as e:
            raise RuntimeError(f"添加向量到Milvus失败: {str(e)}")

    def query_similar(self, query_embeddings: List[List[float]], n_results: int = 10,
                     where: Optional[Dict] = None,
                     where_document: Optional[Dict] = None) -> Dict:
        """查询相似向量"""
        try:
            # 构造过滤条件
            filter_expr = None
            if where:
                # 将ChromaDB风格的where条件转换为Milvus过滤表达式
                conditions = []
                for key, value in where.items():
                    if isinstance(value, str):
                        conditions.append(f'metadata["{key}"] == "{value}"')
                    else:
                        conditions.append(f'metadata["{key}"] == {value}')
                if conditions:
                    filter_expr = " and ".join(conditions)

            # 文档内容过滤（Milvus不支持直接的document过滤，需要在metadata中存储相关字段）
            if where_document:
                raise NotImplementedError("where_document filtering is not supported in Milvus implementation")

            # 执行查询
            results = self.client.search(
                collection_name=self.collection_name,
                data=query_embeddings,
                limit=n_results,
                filter=filter_expr,
                output_fields=["metadata", "document"]
            )

            # 转换为ChromaDB兼容的返回格式
            formatted_results = {
                "ids": [],
                "distances": [],
                "metadatas": [],
                "documents": []
            }

            for result in results:
                batch_ids = []
                batch_distances = []
                batch_metadatas = []
                batch_documents = []

                for hit in result:
                    batch_ids.append(hit["id"])
                    batch_distances.append(hit["distance"])
                    batch_metadatas.append(hit["entity"]["metadata"])
                    batch_documents.append(hit["entity"]["document"])

                formatted_results["ids"].append(batch_ids)
                formatted_results["distances"].append(batch_distances)
                formatted_results["metadatas"].append(batch_metadatas)
                formatted_results["documents"].append(batch_documents)

            return formatted_results
        except Exception as e:
            raise RuntimeError(f"查询Milvus相似向量失败: {str(e)}")

    def delete_embeddings(self, ids: Optional[List[str]] = None,
                         where: Optional[Dict] = None,
                         where_document: Optional[Dict] = None) -> None:
        """删除向量"""
        try:
            if ids:
                # 按ID删除
                self.client.delete(
                    collection_name=self.collection_name,
                    pks=ids
                )
            elif where:
                # 按过滤条件删除
                conditions = []
                for key, value in where.items():
                    if isinstance(value, str):
                        conditions.append(f'metadata["{key}"] == "{value}"')
                    else:
                        conditions.append(f'metadata["{key}"] == {value}')
                filter_expr = " and ".join(conditions)

                self.client.delete(
                    collection_name=self.collection_name,
                    filter=filter_expr
                )
            else:
                raise ValueError("Either ids or where must be provided for deletion")

            if where_document:
                raise NotImplementedError("where_document deletion is not supported in Milvus implementation")
        except Exception as e:
            raise RuntimeError(f"删除Milvus向量失败: {str(e)}")

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        try:
            stats = self.client.get_collection_stats(self.collection_name)
            return {
                "count": stats["row_count"],
                "name": self.collection_name,
                "metadata": self.collection.schema.description
            }
        except Exception as e:
            raise RuntimeError(f"获取Milvus集合统计失败: {str(e)}")

    def create_index(self, field_name: str, index_type: str, params: Dict) -> None:
        """创建索引"""
        try:
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name=field_name,
                index_type=index_type,
                params=params
            )

            self.client.create_index(
                collection_name=self.collection_name,
                index_params=index_params
            )
        except Exception as e:
            raise RuntimeError(f"创建Milvus索引失败: {str(e)}")

    def load_collection(self) -> None:
        """加载集合到内存"""
        try:
            self.client.load_collection(self.collection_name)
        except Exception as e:
            raise RuntimeError(f"加载Milvus集合失败: {str(e)}")

    def release_collection(self) -> None:
        """释放集合内存"""
        try:
            self.client.release_collection(self.collection_name)
        except Exception as e:
            raise RuntimeError(f"释放Milvus集合失败: {str(e)}")


def get_milvus_client():
    """获取Milvus客户端实例"""
    return MilvusClientWrapper()