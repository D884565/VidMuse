from typing import List, Dict, Optional
import uuid
from qdrant_client import QdrantClient as Qdrant
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.v1.app.config.config import settings
from .base import VectorDatabase

# 用于生成确定性UUID的命名空间
QDRANT_UUID_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')


class QdrantClient(VectorDatabase):
    """Qdrant 向量数据库客户端封装"""
    _instance = None
    _client = None  # 共享的Qdrant客户端连接

    def __new__(cls, collection_name: str = None):
        """支持指定collection的实例创建"""
        if collection_name is None and cls._instance is not None:
            # 返回默认collection的单例
            return cls._instance

        instance = super().__new__(cls)
        instance._initialized = False
        instance.collection_name = collection_name or settings.QDRANT_COLLECTION

        if collection_name is None:
            # 保存默认collection的实例为单例
            cls._instance = instance

        return instance

    def __init__(self, collection_name: str = None):
        """初始化客户端（连接仅初始化一次）"""
        if self._initialized:
            return

        # 初始化共享的Qdrant客户端连接
        if QdrantClient._client is None:
            try:
                # 仅当API密钥非空时才传递
                qdrant_kwargs = {
                    "host": settings.QDRANT_HOST,
                    "port": settings.QDRANT_PORT,
                    "grpc_port": settings.QDRANT_GRPC_PORT,
                    "prefer_grpc": settings.QDRANT_PREFER_GRPC,
                    "https": False,
                }
                if settings.QDRANT_API_KEY and settings.QDRANT_API_KEY.strip():
                    qdrant_kwargs["api_key"] = settings.QDRANT_API_KEY

                QdrantClient._client = Qdrant(**qdrant_kwargs)
            except Exception as e:
                raise RuntimeError(f"连接Qdrant失败: {str(e)}")

        self.client = QdrantClient._client
        self.vector_dimension = settings.QDRANT_VECTOR_DIMENSION

        # 确保集合存在
        self._ensure_collection_exists()

        self._initialized = True

    def _to_qdrant_id(self, id_str: str) -> str | int:
        """
        将任意字符串ID转换为Qdrant支持的格式
        Qdrant支持两种ID格式：无符号整数 或 UUID字符串
        转换规则：
        1. 如果ID可以转换为非负整数，直接使用整数格式（性能更好）
        2. 否则使用UUID v5生成确定性UUID，相同输入总会得到相同输出
        """
        try:
            # 尝试转换为整数
            int_id = int(id_str)
            if int_id >= 0:
                return int_id
        except (ValueError, TypeError):
            pass

        # 转换失败则生成UUID
        return str(uuid.uuid5(QDRANT_UUID_NAMESPACE, str(id_str)))

    def _ensure_collection_exists(self):
        """确保集合存在，不存在则创建"""
        try:
            # 检查集合是否存在
            self.client.get_collection(collection_name=self.collection_name)
        except UnexpectedResponse as e:
            if e.status_code == 404:
                self._create_collection()
            else:
                raise RuntimeError(f"检查Qdrant集合失败: {str(e)}")
        except Exception as e:
            # gRPC 模式下抛出的是 _InactiveRpcError，NOT_FOUND 表示集合不存在
            if "NOT_FOUND" in str(e) or "doesn't exist" in str(e):
                self._create_collection()
            else:
                raise RuntimeError(f"连接Qdrant服务失败: {str(e)}")

    def _create_collection(self):
        """创建Qdrant集合"""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_dimension,
                    distance=models.Distance.COSINE
                ),
                shard_number=2,
                replication_factor=1,
                on_disk_payload=True
            )
        except Exception as create_e:
            raise RuntimeError(f"创建Qdrant集合失败: {str(create_e)}")

    def add_embeddings(self, ids: List[str], embeddings: List[List[float]],
                      metadatas: Optional[List[Dict]] = None,
                      documents: Optional[List[str]] = None) -> None:
        """添加向量到集合"""
        try:
            # 构造插入数据
            points = []
            for i in range(len(ids)):
                point = models.PointStruct(
                    id=self._to_qdrant_id(ids[i]),
                    vector=embeddings[i],
                    payload={
                        "metadata": metadatas[i] if metadatas else {},
                        "document": documents[i] if documents else "",
                        "original_id": ids[i]  # 保存原始ID用于返回
                    }
                )
                points.append(point)

            # 批量插入数据
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        except Exception as e:
            raise RuntimeError(f"添加向量到Qdrant失败: {str(e)}")

    def _convert_where_to_filter(self, where: Dict) -> models.Filter:
        """将ChromaDB风格的where条件转换为Qdrant的Filter"""
        must_conditions = []

        for key, value in where.items():
            # 处理元数据字段，支持嵌套字段用点号分隔
            field_path = f"metadata.{key}"

            if isinstance(value, dict):
                # 处理比较操作符，例如 {"$gt": 100}
                for op, val in value.items():
                    if op == "$gt":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                range=models.Range(gt=val)
                            )
                        )
                    elif op == "$gte":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                range=models.Range(gte=val)
                            )
                        )
                    elif op == "$lt":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                range=models.Range(lt=val)
                            )
                        )
                    elif op == "$lte":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                range=models.Range(lte=val)
                            )
                        )
                    elif op == "$ne":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                match=models.MatchValue(value=val)
                            ).negate()
                        )
                    elif op == "$in":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                match=models.MatchAny(any=val)
                            )
                        )
                    elif op == "$nin":
                        must_conditions.append(
                            models.FieldCondition(
                                key=field_path,
                                match=models.MatchAny(any=val)
                            ).negate()
                        )
            else:
                # 精确匹配
                must_conditions.append(
                    models.FieldCondition(
                        key=field_path,
                        match=models.MatchValue(value=value)
                    )
                )

        return models.Filter(must=must_conditions) if must_conditions else None

    def query_similar(self, query_embeddings: List[List[float]], n_results: int = 10,
                     where: Optional[Dict] = None,
                     where_document: Optional[Dict] = None) -> Dict:
        """查询相似向量"""
        try:
            # 构造过滤条件
            query_filter = None
            if where:
                query_filter = self._convert_where_to_filter(where)

            # 文档内容过滤
            if where_document:
                # 处理 $contains 操作
                if "$contains" in where_document:
                    doc_filter = models.FieldCondition(
                        key="document",
                        match=models.MatchText(text=where_document["$contains"])
                    )
                    if query_filter:
                        query_filter.must.append(doc_filter)
                    else:
                        query_filter = models.Filter(must=[doc_filter])

            # 执行批量查询
            all_results = []
            for embedding in query_embeddings:
                search_result = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=embedding,
                    limit=n_results,
                    query_filter=query_filter,
                    with_payload=True,
                    with_vectors=False
                )
                all_results.append(search_result)

            # 转换为ChromaDB兼容的返回格式
            formatted_results = {
                "ids": [],
                "distances": [],
                "metadatas": [],
                "documents": []
            }

            for result in all_results:
                batch_ids = []
                batch_distances = []
                batch_metadatas = []
                batch_documents = []

                for hit in result:
                    # 返回原始ID而不是转换后的UUID
                    original_id = hit.payload.get("original_id", hit.id)
                    batch_ids.append(original_id)
                    batch_distances.append(hit.score)
                    batch_metadatas.append(hit.payload.get("metadata", {}))
                    batch_documents.append(hit.payload.get("document", ""))

                formatted_results["ids"].append(batch_ids)
                formatted_results["distances"].append(batch_distances)
                formatted_results["metadatas"].append(batch_metadatas)
                formatted_results["documents"].append(batch_documents)

            return formatted_results
        except Exception as e:
            raise RuntimeError(f"查询Qdrant相似向量失败: {str(e)}")

    def delete_embeddings(self, ids: Optional[List[str]] = None,
                         where: Optional[Dict] = None,
                         where_document: Optional[Dict] = None) -> None:
        """删除向量"""
        try:
            if ids:
                # 按ID删除，需要转换为Qdrant支持的UUID格式
                qdrant_ids = [self._to_qdrant_id(id) for id in ids]
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=qdrant_ids)
                )
            elif where:
                # 按过滤条件删除
                query_filter = self._convert_where_to_filter(where)

                # 文档内容过滤
                if where_document:
                    if "$contains" in where_document:
                        doc_filter = models.FieldCondition(
                            key="document",
                            match=models.MatchText(text=where_document["$contains"])
                        )
                        if query_filter:
                            query_filter.must.append(doc_filter)
                        else:
                            query_filter = models.Filter(must=[doc_filter])

                if query_filter:
                    self.client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.FilterSelector(filter=query_filter)
                    )
                else:
                    raise ValueError("无效的过滤条件")
            else:
                raise ValueError("Either ids or where must be provided for deletion")
        except Exception as e:
            raise RuntimeError(f"删除Qdrant向量失败: {str(e)}")

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        try:
            collection_info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "count": collection_info.points_count,
                "name": self.collection_name,
                "metadata": {
                    "vector_dimension": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance,
                    "indexed": collection_info.status == "green",
                    "shard_number": collection_info.config.params.shard_number,
                    "replication_factor": collection_info.config.params.replication_factor
                }
            }
        except Exception as e:
            raise RuntimeError(f"获取Qdrant集合统计失败: {str(e)}")

    def create_index(self, field_name: str, index_type: str, params: Dict) -> None:
        """创建索引"""
        try:
            if field_name == "document_embedding" or field_name == "vector":
                # 创建向量索引
                self.client.create_index(
                    collection_name=self.collection_name,
                    field_name="vector",
                    index_type=index_type,
                    index_params=params
                )
            else:
                # 创建payload索引
                field_path = f"metadata.{field_name}" if field_name != "document" else "document"
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_path,
                    field_schema=params.get("schema_type", models.PayloadSchemaType.KEYWORD)
                )
        except Exception as e:
            raise RuntimeError(f"创建Qdrant索引失败: {str(e)}")

    def load_collection(self) -> None:
        """加载集合 - Qdrant自动管理，无需显式加载"""
        # Qdrant集合默认加载到内存，无需手动操作
        pass

    def release_collection(self) -> None:
        """释放集合内存 - Qdrant自动管理，无需显式释放"""
        # Qdrant自动管理内存，无需手动操作
        pass

    def get_all(self, limit: int = 1000, offset: int = 0, with_vectors: bool = True) -> Dict:
        """
        批量获取集合中的所有向量
        :param limit: 每次获取的数量
        :param offset: 偏移量（Qdrant scroll不支持offset，使用last_point_id进行分页）
        :param with_vectors: 是否返回向量数据
        :return: 包含ids、vectors、metadatas、documents的字典
        """
        try:
            all_points = []
            last_point_id = None

            while True:
                # 使用scroll API滚动获取所有点
                search_result, next_page_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=limit,
                    offset=last_point_id,
                    with_payload=True,
                    with_vectors=with_vectors
                )

                all_points.extend(search_result)

                if next_page_offset is None:
                    break

                last_point_id = next_page_offset

            # 转换为统一格式
            formatted_results = {
                "ids": [],
                "vectors": [],
                "metadatas": [],
                "documents": []
            }

            for point in all_points:
                # 返回原始ID而不是转换后的UUID
                original_id = point.payload.get("original_id", str(point.id))
                formatted_results["ids"].append(original_id)
                if with_vectors:
                    formatted_results["vectors"].append(point.vector)
                formatted_results["metadatas"].append(point.payload.get("metadata", {}))
                formatted_results["documents"].append(point.payload.get("document", ""))

            return formatted_results
        except Exception as e:
            raise RuntimeError(f"获取Qdrant所有向量失败: {str(e)}")


def get_qdrant_client(collection_name: str = None):
    """获取Qdrant客户端实例"""
    return QdrantClient(collection_name)
