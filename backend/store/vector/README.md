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
- `PRODUCT_COLLECTION`: 商品知识库集合名称
- `SLICE_COLLECTION`: 片段知识库集合名称
- `VIDEO_COLLECTION`: 视频知识库集合名称
- `IMG_COLLECTION`: 图片知识库集合名称
- `AUDIO_COLLECTION`: 音频知识库集合名称

### Milvus配置
- `MILVUS_HOST`: Milvus服务地址
- `MILVUS_PORT`: Milvus服务端口（默认19530）
- `MILVUS_USERNAME`: Milvus用户名（可选）
- `MILVUS_PASSWORD`: Milvus密码（可选）
- `MILVUS_PRODUCT_COLLECTION`: 商品知识库集合名称
- `MILVUS_SLICE_COLLECTION`: 片段知识库集合名称
- `MILVUS_VIDEO_COLLECTION`: 视频知识库集合名称
- `MILVUS_IMG_COLLECTION`: 图片知识库集合名称
- `MILVUS_AUDIO_COLLECTION`: 音频知识库集合名称
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
