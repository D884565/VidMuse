# 可插拔组件系统使用指南

## 概述
将原有的`query_enhancement`、`retrieval`、`post_processing`三个模块重构为可插拔组件系统，支持动态选择和配置组件，由工具层进行编排选择。

## 核心架构

### 组件类型
系统支持三种类型的可插拔组件：
1. **查询增强器（Query Enhancer）**：对用户查询进行预处理，如上下文处理、意图识别、查询重写等
2. **检索器（Retriever）**：执行实际的检索操作，如向量检索、关键词检索、混合检索等
3. **后处理器（Post Processor）**：对检索结果进行后处理，如去重、过滤、合并、重排序等

### 组件注册中心
`component_registry`是全局组件注册中心，负责：
- 自动发现和注册所有组件
- 提供组件的实例化和获取
- 支持创建处理流水线

## 使用方法

### 1. 查看可用组件
```python
from backend.v1.app.search import component_registry

# 列出所有查询增强器
print("查询增强器:", component_registry.list_components("query_enhancer"))

# 列出所有检索器
print("检索器:", component_registry.list_components("retriever"))

# 列出所有后处理器
print("后处理器:", component_registry.list_components("post_processor"))
```

### 2. 单独使用组件
```python
# 获取单个组件实例
intent_recognizer = component_registry.get_query_enhancer("intent")
vector_retriever = component_registry.get_retriever("vector")
deduplicator = component_registry.get_post_processor("deduplicator")

# 使用组件
enhanced_query = intent_recognizer.enhance(query, context)
documents = vector_retriever.retrieve(query, top_k=10)
processed_docs = deduplicator.process(documents, query)
```

### 3. 创建处理流水线
```python
# 创建查询增强流水线
enhancers = component_registry.create_query_enhancer_pipeline([
    "context", 
    "intent", 
    "rewrite", 
    "expander"
])

# 执行流水线
query = Query(text="用户查询")
for enhancer in enhancers:
    query = enhancer.enhance(query, context)

# 创建后处理流水线
processors = component_registry.create_post_processor_pipeline([
    "deduplicator",
    "filter",
    "reranker"
])

# 执行流水线
for processor in processors:
    documents = processor.process(documents, query)
```

### 4. 自定义工具组件配置
每个搜索工具可以通过类属性配置要使用的组件：

```python
class CustomSearchTool(BaseSearchTool):
    # 配置查询增强流水线
    query_enhancer_config = [
        "context",          # 使用默认配置的上下文处理器
        ("intent", {"config_key": "value"}),  # 带自定义配置的意图识别器
        "rewrite"
    ]
    
    # 配置检索器
    retriever_config = {
        "semantic": "vector",               # 别名: 组件名称
        "keyword": ("keyword", {})          # 别名: (组件名称, 配置)
    }
    
    # 配置后处理流水线
    post_processor_config = [
        "deduplicator",
        ("filter", {"min_score": 0.7})      # 带自定义配置的过滤器
    ]
```

## 组件列表

### 查询增强器（Query Enhancer）
| 组件名称 | 说明 |
|---------|------|
| `context` | 上下文处理器 |
| `intent` | 意图识别器 |
| `rewrite` | 查询重写器 |
| `expander` | 查询扩展器 |

### 检索器（Retriever）
| 组件名称 | 说明 |
|---------|------|
| `vector` | 向量检索器（Milvus） |
| `chromadb` | ChromaDB向量检索器 |
| `keyword` | 关键词检索器 |
| `hybrid` | 混合检索器 |
| `sql` | SQL检索器 |
| `api` | API检索器 |

### 后处理器（Post Processor）
| 组件名称 | 说明 |
|---------|------|
| `deduplicator` | 去重处理器 |
| `filter` | 结果过滤器 |
| `merger` | 结果合并器 |
| `reranker` | 结果重排器 |

## 扩展新组件

### 步骤1：实现组件类
```python
# 在对应模块下创建新的组件类，继承自对应基类
class CustomQueryEnhancer(BaseQueryEnhancer):
    def enhance(self, query: Query, context: Optional[SearchContext] = None) -> Query:
        # 自定义处理逻辑
        return query
```

### 步骤2：自动注册
组件会被自动发现并注册，注册名称为类名的蛇形形式（去掉后缀）：
- 类名`CustomQueryEnhancer` → 注册名称`custom`

### 步骤3：使用新组件
```python
# 在工具配置中使用
query_enhancer_config = [
    "custom"  # 使用新组件
]

# 或者直接获取
enhancer = component_registry.get_query_enhancer("custom")
```

## 工具配置示例

### 通用检索工具（完整流水线）
```python
query_enhancer_config = ["context", "intent", "rewrite", "expander"]
retriever_config = {
    "semantic": "vector",
    "keyword": "keyword", 
    "hybrid": "hybrid",
    "sql": "sql",
    "api": "api"
}
post_processor_config = ["deduplicator", "filter", "merger", "reranker"]
```

### 语义检索工具（简化流水线）
```python
query_enhancer_config = ["context"]  # 仅需要上下文处理
retriever_config = {
    "milvus": "vector",
    "chromadb": "chromadb"
}
post_processor_config = ["deduplicator", "filter", "merger", "reranker"]
```

### 关键词检索工具（轻量流水线）
```python
query_enhancer_config = ["rewrite", "expander"]
retriever_config = {"keyword": "keyword"}
post_processor_config = ["deduplicator", "filter"]
```
