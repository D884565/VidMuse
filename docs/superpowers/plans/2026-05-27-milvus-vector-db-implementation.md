# Milvus向量数据库对接实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成Milvus向量数据库的对接，实现统一的向量数据库抽象层，支持通过配置切换ChromaDB和Milvus。

**Architecture:** 基于抽象基类设计，定义统一的VectorDatabase接口，ChromaDB和Milvus分别实现该接口，通过工厂模式根据配置返回对应的客户端实例。

**Tech Stack:** Python 3.12+, pymilvus (Milvus SDK), chromadb, abc (抽象基类)

---

### Task 1: 创建向量数据库抽象基类

**Files:**
- Create: `backend/store/vector/base.py`

- [ ] **Step 1: 编写抽象基类代码**

```python
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
```

- [ ] **Step 2: 验证语法正确性**

Run: `python -m pytest backend/store/vector/base.py -v --no-header`
Expected: No syntax errors, 0 tests collected (expected for abstract class)

- [ ] **Step 3: Commit**

```bash
git add backend/store/vector/base.py
git commit -m "feat: add vector database abstract base class"
```

---

### Task 2: 适配现有ChromaDB客户端到抽象基类

**Files:**
- Modify: `backend/store/vector/chromadb_client.py`

- [ ] **Step 1: 修改ChromaDBClient继承VectorDatabase**

```python
import chromadb
from chromadb import Settings

from backend.v1.app.config.config import settings
from .base import VectorDatabase


class ChromaDBClient(VectorDatabase):
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
        self.client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self._ensure_collection_exists()
        self._initialized = True

    def _ensure_collection_exists(self):
        """确保集合存在，不存在则创建"""
        try:
            collection = self.client.get_collection(name=settings.CHROMADB_COLLECTION)
        except Exception:
            collection = self.client.create_collection(
                name=settings.CHROMADB_COLLECTION,
                metadata={"description": "视频内容向量存储集合"},
            )
        return collection

    def add_embeddings(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict] = None, documents: list[str] = None):
        """添加向量到集合"""
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
        """查询相似向量"""
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
        """删除向量"""
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

    def create_index(self, field_name: str, index_type: str, params: Dict) -> None:
        """创建索引 - ChromaDB不支持，抛出未实现错误"""
        raise NotImplementedError("ChromaDB does not support explicit index creation")

    def load_collection(self) -> None:
        """加载集合 - ChromaDB不支持，抛出未实现错误"""
        raise NotImplementedError("ChromaDB does not support collection loading")

    def release_collection(self) -> None:
        """释放集合 - ChromaDB不支持，抛出未实现错误"""
        raise NotImplementedError("ChromaDB does not support collection releasing")


def get_chromadb_client():
    """获取ChromaDB客户端实例"""
    return ChromaDBClient()
```

- [ ] **Step 2: 验证修改正确性**

Run: `python -c "from backend.store.vector.chromadb_client import ChromaDBClient; print('ChromaDBClient import success')"`
Expected: "ChromaDBClient import success"

- [ ] **Step 3: Commit**

```bash
git add backend/store/vector/chromadb_client.py
git commit -m "feat: adapt ChromaDBClient to VectorDatabase abstract class"
```

---

### Task 3: 实现Milvus客户端

**Files:**
- Create: `backend/store/vector/milvus_client.py`

- [ ] **Step 1: 编写Milvus客户端代码**

```python
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
        
        # 定义集合schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dimension),
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
                    "embedding": embeddings[i],
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
```

- [ ] **Step 2: 验证语法正确性**

Run: `python -c "from backend.store.vector.milvus_client import MilvusClientWrapper; print('MilvusClientWrapper import success')"`
Expected: "MilvusClientWrapper import success" (connection errors are expected if Milvus is not running locally)

- [ ] **Step 3: Commit**

```bash
git add backend/store/vector/milvus_client.py
git commit -m "feat: implement Milvus vector database client"
```

---

### Task 4: 实现向量数据库工厂类

**Files:**
- Create: `backend/store/vector/factory.py`

- [ ] **Step 1: 编写工厂类代码**

```python
from typing import Optional

from backend.v1.app.config.config import settings
from .base import VectorDatabase
from .chromadb_client import get_chromadb_client
from .milvus_client import get_milvus_client


class VectorDBType:
    """向量数据库类型枚举"""
    CHROMADB = "chromadb"
    MILVUS = "milvus"


def get_vector_db_client(db_type: Optional[str] = None) -> VectorDatabase:
    """
    获取向量数据库客户端实例
    :param db_type: 向量数据库类型，默认从配置中读取
    :return: 向量数据库客户端实例
    """
    if db_type is None:
        db_type = getattr(settings, "VECTOR_DB_TYPE", VectorDBType.CHROMADB)
    
    if db_type == VectorDBType.CHROMADB:
        return get_chromadb_client()
    elif db_type == VectorDBType.MILVUS:
        return get_milvus_client()
    else:
        raise ValueError(f"不支持的向量数据库类型: {db_type}")
```

- [ ] **Step 2: 验证语法正确性**

Run: `python -c "from backend.store.vector.factory import get_vector_db_client, VectorDBType; print('Factory import success')"`
Expected: "Factory import success"

- [ ] **Step 3: Commit**

```bash
git add backend/store/vector/factory.py
git commit -m "feat: add vector database factory"
```

---

### Task 5: 添加Milvus相关配置项

**Files:**
- Modify: `backend/v1/app/config/config.py`

- [ ] **Step 1: 在配置类中添加Milvus配置**

找到CHROMADB配置的位置（大约69行），添加以下配置：

```python
    # 向量数据库配置
    VECTOR_DB_TYPE: str = "chromadb"  # 可选值: chromadb, milvus
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8001
    CHROMADB_COLLECTION: str = "vidmuse_vectors"
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USERNAME: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION: str = "vidmuse_vectors"
    MILVUS_VECTOR_DIMENSION: int = 1536  # 默认OpenAI embedding维度
```

注意：如果原配置中没有CHROMADB_COLLECTION，需要一并添加。

- [ ] **Step 2: 验证配置加载**

Run: `python -c "from backend.v1.app.config.config import settings; print(f'VECTOR_DB_TYPE: {settings.VECTOR_DB_TYPE}'); print(f'MILVUS_HOST: {settings.MILVUS_HOST}')"`
Expected: 
```
VECTOR_DB_TYPE: chromadb
MILVUS_HOST: localhost
```

- [ ] **Step 3: Commit**

```bash
git add backend/v1/app/config/config.py
git commit -m "feat: add Milvus configuration items"
```

---

### Task 6: 更新vector包的导出接口

**Files:**
- Modify: `backend/store/vector/__init__.py`

- [ ] **Step 1: 更新__init__.py内容**

```python
from .base import VectorDatabase
from .factory import get_vector_db_client, VectorDBType
from .chromadb_client import ChromaDBClient, get_chromadb_client
from .milvus_client import MilvusClientWrapper as MilvusClient, get_milvus_client

__all__ = [
    "VectorDatabase",
    "get_vector_db_client", 
    "VectorDBType",
    "ChromaDBClient",
    "get_chromadb_client",
    "MilvusClient",
    "get_milvus_client"
]
```

- [ ] **Step 2: 验证包导出**

Run: `python -c "from backend.store.vector import *; print('All exports success'); print(f'Available types: {[name for name in dir() if not name.startswith(\"_\")]}')"`
Expected: 无错误，显示所有导出的类和函数

- [ ] **Step 3: Commit**

```bash
git add backend/store/vector/__init__.py
git commit -m "feat: update vector package exports"
```

---

### Task 7: 添加依赖说明和使用示例

**Files:**
- Create: `backend/store/vector/README.md`

- [ ] **Step 1: 编写使用说明文档**

```markdown
# 向量数据库使用说明

## 概述
本模块提供了统一的向量数据库接口，支持ChromaDB和Milvus两种实现，可以通过配置灵活切换。

## 依赖安装

### ChromaDB依赖
```bash
pip install chromadb
```

### Milvus依赖
```bash
pip install pymilvus>=2.3.0
```

## 配置说明

在配置文件中设置以下参数：

### 通用配置
- `VECTOR_DB_TYPE`: 向量数据库类型，可选值 `chromadb`（默认）或 `milvus`

### ChromaDB配置
- `CHROMADB_HOST`: ChromaDB服务地址
- `CHROMADB_PORT`: ChromaDB服务端口
- `CHROMADB_COLLECTION`: 集合名称

### Milvus配置
- `MILVUS_HOST`: Milvus服务地址
- `MILVUS_PORT`: Milvus服务端口（默认19530）
- `MILVUS_USERNAME`: Milvus用户名（可选）
- `MILVUS_PASSWORD`: Milvus密码（可选）
- `MILVUS_COLLECTION`: 集合名称
- `MILVUS_VECTOR_DIMENSION`: 向量维度（默认1536，对应OpenAI embedding）

## 使用示例

### 基本使用（推荐，通过工厂获取客户端）
```python
from backend.store.vector import get_vector_db_client

# 获取客户端实例（根据配置自动选择）
vector_db = get_vector_db_client()

# 添加向量
ids = ["id1", "id2"]
embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
metadatas = [{"video_id": "vid1", "timestamp": 1.0}, {"video_id": "vid2", "timestamp": 2.0}]
documents = ["内容1", "内容2"]

vector_db.add_embeddings(ids, embeddings, metadatas, documents)

# 查询相似向量
query_embedding = [[0.15, 0.25, 0.35]]
results = vector_db.query_similar(query_embedding, n_results=2)
print(results)

# 删除向量
vector_db.delete_embeddings(ids=["id1"])

# 获取集合统计
stats = vector_db.get_collection_stats()
print(stats)
```

### Milvus特有功能使用
```python
from backend.store.vector import get_vector_db_client, VectorDBType

# 显式获取Milvus客户端
milvus_db = get_vector_db_client(db_type=VectorDBType.MILVUS)

# 创建自定义索引
milvus_db.create_index(
    field_name="embedding",
    index_type="IVF_SQ8",
    params={"nlist": 2048}
)

# 手动加载/释放集合
milvus_db.release_collection()
milvus_db.load_collection()
```

### 直接使用特定客户端
```python
from backend.store.vector import ChromaDBClient, MilvusClient

# 直接使用ChromaDB
chroma_client = ChromaDBClient()

# 直接使用Milvus
milvus_client = MilvusClient()
```

## 兼容性说明

### ChromaDB vs Milvus接口差异
1. `where_document`过滤：Milvus实现暂不支持该参数，需要将相关过滤条件放到metadata中
2. 过滤语法：ChromaDB的where条件会自动转换为Milvus的过滤表达式，支持基本的等于比较
3. 距离计算：ChromaDB默认使用余弦相似度，Milvus默认使用L2距离，结果中的distance值含义不同

## 注意事项
1. Milvus需要单独部署服务，ChromaDB可以使用本地模式或服务模式
2. 向量维度需要和embedding模型输出保持一致
3. 大量数据插入建议分批进行，单次插入不要超过1000条
```

- [ ] **Step 2: Commit**

```bash
git add backend/store/vector/README.md
git commit -m "docs: add vector database usage documentation"
```

---

## 验证和测试

### Task 8: 验证完整功能

- [ ] **Step 1: 验证工厂切换功能**
```python
from backend.store.vector import get_vector_db_client, VectorDBType

# 测试ChromaDB客户端
chroma_client = get_vector_db_client(db_type=VectorDBType.CHROMADB)
assert chroma_client is not None
print("ChromaDB client created successfully")

# 测试Milvus客户端
milvus_client = get_vector_db_client(db_type=VectorDBType.MILVUS)
assert milvus_client is not None
print("Milvus client created successfully")
```

- [ ] **Step 2: 验证统一接口兼容性**
确保所有客户端都实现了VectorDatabase接口的所有方法。

- [ ] **Step 3: 运行现有测试（如果有）**
确保现有使用ChromaDB的功能不受影响。
