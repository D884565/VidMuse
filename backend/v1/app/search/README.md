# RAG检索系统使用文档

## 概述
这是一套完整的独立RAG检索体系，支持多种数据源、多种检索方式，包含问题增强和结果后处理能力。

## 功能特性
### 1. 问题增强
- 上下文处理：结合多轮对话历史补全查询语义
- 意图识别：自动识别查询意图，选择合适的检索方式
- Query重写：优化查询表述，提高检索准确率
- Query扩展：扩展同义词和相关关键词，提高召回率

### 2. 检索通道
- 向量检索：支持Milvus、ChromaDB等向量数据库的语义检索
- 关键词检索：支持Elasticsearch等全文检索引擎
- 混合检索：结合语义检索和关键词检索的优势
- SQL检索：支持关系型数据库的结构化查询
- API检索：支持调用外部API获取结果

### 3. 结果后处理
- 结果去重：移除重复的检索结果
- 结果过滤：基于阈值、关键词等过滤不相关结果
- 结果合并：融合多数据源的检索结果
- 结果重排序：基于语义或业务规则重新排序

## 快速开始

### 1. 基本使用
```python
from backend.v1.app.search import SearchService

# 初始化检索服务
search_service = SearchService()

# 执行检索
result = search_service.search("你的查询文本")

# 处理结果
if result.success:
    print(f"找到{len(result.documents)}个结果")
    for doc in result.documents:
        print(f"标题: {doc.title}")
        print(f"内容: {doc.content}")
        print(f"得分: {doc.score}")
        print(f"来源: {doc.source_type}")
else:
    print(f"检索失败: {result.error_msg}")
```

### 2. 带上下文的检索
```python
from backend.v1.app.search import SearchService, SearchContext

search_service = SearchService()

# 构建对话上下文
context = SearchContext(
    conversation_history=[
        {"role": "user", "content": "什么是向量数据库？"},
        {"role": "assistant", "content": "向量数据库是专门用于存储和查询向量的数据库..."},
    ],
    user_id="user123",
    session_id="session456"
)

# 执行带上下文的检索
result = search_service.search("它有什么优势？", context=context)
```

### 3. 指定检索类型
```python
# 强制使用关键词检索
result = search_service.search("查找相关文档", retrieval_type="keyword")

# 强制使用SQL检索
result = search_service.search("统计用户数量", retrieval_type="sql")
```

### 4. 自定义配置
```python
from backend.v1.app.search import SearchService

# 自定义配置
custom_config = {
    "retrieval": {
        "default_top_k": 20,
        "min_score_threshold": 0.7
    },
    "post_processing": {
        "enable_reranking": True,
        "rerank_top_k": 30
    }
}

search_service = SearchService(custom_config)
```

## 架构说明
系统采用模块化分层架构：
- **核心层**：定义统一的接口和数据模型
- **问题增强层**：处理查询的增强和优化
- **检索通道层**：实现各种数据源的检索逻辑
- **后处理层**：对检索结果进行加工处理
- **服务层**：对外提供统一的检索接口

## 扩展开发
### 新增数据源通道
1. 继承`BaseDataSourceChannel`抽象类
2. 实现`connect`、`disconnect`、`is_connected`方法
3. 实现具体的查询方法
4. 在对应的检索器中集成新的通道

### 新增问题增强功能
1. 继承`BaseQueryEnhancerImpl`基类
2. 实现`_enhance`方法
3. 在`SearchService`的`_init_query_enhancers`方法中添加新的增强器

### 新增后处理功能
1. 继承`BasePostProcessorImpl`基类
2. 实现`_process`方法
3. 在`SearchService`的`_init_post_processors`方法中添加新的后处理器

## 配置说明
所有配置都在`config.py`文件中，可以根据实际需求进行调整：
- `DATA_SOURCE_CONFIG`：各数据源的连接配置
- `RETRIEVAL_CONFIG`：检索相关的配置
- `QUERY_ENHANCEMENT_CONFIG`：问题增强相关的配置
- `POST_PROCESSING_CONFIG`：后处理相关的配置