---
name: milvus-vector-db-integration
description: Milvus向量数据库对接设计文档，实现统一的向量数据库抽象层
metadata:
  type: project
---

# Milvus向量数据库对接设计文档

## 项目背景
项目需要在store包下完成向量型数据库Milvus的对接，同时为了方便后续切换不同的向量数据库实现，需要设计统一的抽象层。

## 设计目标
1. 实现Milvus向量数据库的完整功能对接
2. 设计统一的向量数据库抽象接口，兼容现有ChromaDB和新增的Milvus
3. 提供工厂模式，通过配置即可切换使用的向量数据库
4. 支持Milvus特有的扩展功能

## 架构设计

### 1. 抽象基类
定义`VectorDatabase`抽象基类，包含统一的接口方法：
- `add_embeddings`: 添加向量到数据库
- `query_similar`: 查询相似向量
- `delete_embeddings`: 删除向量
- `get_collection_stats`: 获取集合统计信息
- 扩展方法（Milvus特有）:
  - `create_index`: 创建索引
  - `load_collection`: 加载集合到内存
  - `release_collection`: 释放集合内存

### 2. 实现类
- **ChromaDBClient**: 现有ChromaDB客户端，修改为继承`VectorDatabase`抽象基类，扩展方法抛出`NotImplementedError`
- **MilvusClient**: 新增Milvus客户端，实现所有抽象基类方法和扩展方法

### 3. 工厂模式
实现`get_vector_db_client()`工厂函数，根据配置的`VECTOR_DB_TYPE`返回对应的客户端实例：
- `chromadb`: 返回ChromaDBClient实例
- `milvus`: 返回MilvusClient实例

### 4. 配置项
新增以下配置项：
```python
VECTOR_DB_TYPE: str = "chromadb"  # 向量数据库类型
MILVUS_HOST: str = "localhost"    # Milvus服务地址
MILVUS_PORT: int = 19530          # Milvus服务端口
MILVUS_USERNAME: str = ""         # Milvus用户名
MILVUS_PASSWORD: str = ""         # Milvus密码
MILVUS_COLLECTION: str = "vidmuse_vectors"  # Milvus集合名称
MILVUS_VECTOR_DIMENSION: int = 1536  # 向量维度
```

## 接口规范

### 统一接口参数说明
#### add_embeddings
- `ids`: 向量ID列表
- `embeddings`: 向量数据列表，每个元素是float数组
- `metadatas`: 元数据列表，每个元素是字典
- `documents`: 文档内容列表

#### query_similar
- `query_embeddings`: 查询向量列表
- `n_results`: 返回结果数量
- `where`: 元数据过滤条件
- `where_document`: 文档内容过滤条件
- 返回: 包含ids、distances、metadatas、documents的字典

#### delete_embeddings
- `ids`: 要删除的向量ID列表
- `where`: 元数据过滤条件
- `where_document`: 文档内容过滤条件

#### get_collection_stats
- 返回: 包含count、name、metadata等统计信息的字典

## 实现步骤
1. 创建向量数据库抽象基类`backend/store/vector/base.py`
2. 修改现有ChromaDBClient继承抽象基类
3. 实现Milvus客户端`backend/store/vector/milvus_client.py`
4. 实现工厂类`backend/store/vector/factory.py`
5. 在配置文件中添加Milvus相关配置项
6. 更新`backend/store/vector/__init__.py`导出相关类和函数
7. 编写单元测试验证功能

## 注意事项
1. 保持接口兼容性，现有使用ChromaDB的代码无需修改
2. Milvus实现需要处理连接池、重试等异常情况
3. 集合创建和索引创建需要考虑幂等性
4. 错误信息需要统一格式，便于上层处理
