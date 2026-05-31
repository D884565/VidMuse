# Agent观测系统使用说明

## 概述
Agent观测系统会自动记录所有Agent的推理过程，包括用户输入、模型调用、工具调用、返回结果等完整信息，存储在`agent_traces`单表中，便于问题排查、效果分析和用户行为研究。

## 配置说明
在`backend/v1/app/search/agent_config.py`中可以配置观测系统行为：

```python
"tracing": {
    "enabled": True,  # 是否启用推理轨迹落库，默认True
    "async_save": True,  # 是否异步保存，默认True（同步WSGI环境下建议设为False）
    "save_system_prompt": True  # 是否保存系统提示词到轨迹，默认True
}
```

## 快速使用

### 1. 基础使用（无需修改现有代码）
现有调用代码完全兼容，所有Agent调用会自动记录轨迹：

```python
from backend.v1.app.search import agent_service

# 创建会话
session_id = agent_service.create_session(user_id="123")

# 发送消息，自动记录轨迹
response = agent_service.chat(session_id, "什么是向量数据库？")

print(response.answer)
```

### 2. 关联项目ID
如果需要关联项目信息，创建会话时传入project_id：

```python
session_id = agent_service.create_session(
    user_id="123",
    project_id=456,  # 项目ID会自动保存到轨迹中
    metadata={"user_role": "admin"}  # 其他元数据也会被保存
)
```

### 3. 查询轨迹数据

```python
from backend.v1.app.search import trace_storage

# 按轨迹ID查询
trace = await trace_storage.get_trace_by_id(trace_id=1)
if trace:
    print(f"用户问题: {trace.user_input}")
    print(f"回答: {trace.final_answer}")
    print(f"耗时: {trace.cost_time}s")
    print(f"工具调用: {trace.tool_calls}")

# 按会话ID查询所有轨迹
traces = await trace_storage.get_traces_by_session_id(session_id="session_abc123")
for trace in traces:
    print(f"[{trace.created_at}] {trace.user_input} -> {trace.final_answer[:50]}...")

# 按用户ID查询所有轨迹
traces = await trace_storage.get_traces_by_user_id(user_id=123)
```

### 4. 手动保存轨迹（特殊场景）
通常不需要手动调用，系统会自动保存。如果需要自定义保存：

```python
trace_id = await trace_storage.save_trace(
    session_id="session_xxx",
    user_id=123,
    project_id=456,
    user_input="问题",
    system_prompt="系统提示",
    model="doubao-1.5-pro",
    temperature=0.7,
    max_tokens=2000,
    top_p=0.9,
    messages_history=[...],
    iterations=1,
    tool_calls=[...],
    tool_results=[...],
    final_answer="回答",
    cost_time=1.23,
    success=True,
    error_msg=None
)
```

## 表结构说明
所有数据存储在`agent_traces`单表中：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| session_id | VARCHAR(64) | 会话ID（索引） |
| user_id | BIGINT | 用户ID（索引，可选） |
| project_id | BIGINT | 项目ID（索引，可选） |
| user_input | TEXT | 用户原始输入 |
| system_prompt | TEXT | 系统提示词（可配置是否保存） |
| model | VARCHAR(64) | 使用的模型名称 |
| temperature | FLOAT | 模型温度参数 |
| max_tokens | BIGINT | 最大生成长度 |
| top_p | FLOAT | 核采样参数 |
| messages_history | JSON | 完整的消息历史，包括所有工具调用和结果 |
| iterations | BIGINT | ReAct推理迭代次数 |
| tool_calls | JSON | 所有工具调用信息：[{"id": "xxx", "name": "tool_name", "parameters": {...}, "result": "..."}] |
| tool_results | JSON | 所有工具返回结果列表 |
| final_answer | TEXT | 最终返回给用户的回答 |
| cost_time | FLOAT | 执行耗时（秒） |
| success | BOOLEAN | 是否执行成功 |
| error_msg | TEXT | 错误信息（失败时） |
| metadata | JSON | 扩展元数据，来自会话的metadata |
| created_at | DATETIME | 创建时间（索引） |

## 典型使用场景

### 1. 问题排查
当用户反馈回答错误时，可以通过会话ID查询完整的推理过程：
- 查看用户的原始问题
- 查看模型调用的参数
- 查看调用了哪些工具，参数是什么，返回结果是什么
- 查看完整的消息交互历史
- 定位是工具返回错误还是模型合成错误

### 2. 效果分析
- 统计不同模型参数的回答准确率
- 分析工具调用的频率和成功率
- 统计平均响应时间
- 分析用户常见问题类型

### 3. 数据标注
- 导出轨迹数据用于训练数据标注
- 分析 bad case 优化prompt和工具

### 4. 用户行为分析
- 分析用户查询热点
- 统计不同用户群体的使用习惯
- 优化产品功能

## 部署说明

### 1. 创建数据库表
运行迁移脚本创建表结构：
```bash
cd backend
python scripts/add_agent_trace_table.py
```

### 2. 环境配置
- **FastAPI/ASGI环境**：保持`async_save: True`，性能最佳
- **Flask/Django/WSGI环境**：建议设置`async_save: False`，避免事件循环问题
- **开发环境**：可以设置`enabled: False`关闭轨迹保存，提高调试速度

## 注意事项
1. 轨迹保存失败不会影响主问答流程，仅打印错误日志
2. 消息历史和工具调用信息可能包含敏感数据，注意权限控制
3. 数据量大时可以按时间分区或定期归档历史数据
4. 建议定期清理过期的轨迹数据，避免表过大
