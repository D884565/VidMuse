# Agentic RAG 系统使用文档

## 概述
Agentic RAG系统是一个基于大模型和工具调用的智能问答系统，能够自主决定何时检索知识库信息，何时直接回答用户问题。系统将意图识别、上下文管理、检索决策等能力全部交给大模型Agent自主处理，提供更智能、更准确的问答体验。

## 功能特性
- 🤖 **智能Agent**：基于豆包大模型，支持function calling能力
- 🔧 **工具调用**：支持动态调用RAG检索工具，未来可扩展更多工具
- 💬 **多轮对话**：自动管理会话上下文，支持连贯的多轮对话
- 📚 **RAG集成**：无缝集成已有的RAG检索系统，获取知识库信息
- 🔌 **API接口**：提供标准HTTP API，方便其他服务集成
- 🧩 **可扩展架构**：插件式工具设计，新增工具无需修改核心代码

## 快速开始

### 1. 环境配置
确保以下环境变量已配置（通常在项目根目录的.env文件中）：
```env
# 豆包API密钥
DOUBAO_SEED_API_KEY=your_api_key_here
```

### 2. 接口使用

#### 2.1 创建会话
```http
POST /v1/agent/session
Content-Type: application/json

{
    "user_id": "user_123",
    "metadata": {
        "platform": "web",
        "version": "1.0.0"
    }
}
```

**响应：**
```json
{
    "code": "0000000",
    "message": "会话创建成功",
    "data": {
        "session_id": "session_abc123def456",
        "created_at": "2024-01-01T12:00:00"
    }
}
```

#### 2.2 发送消息聊天
```http
POST /v1/agent/chat
Content-Type: application/json

{
    "session_id": "session_abc123def456",
    "message": "什么是向量数据库？",
    "stream": false,
    "tool_call_enabled": true
}
```

**响应（无工具调用）：**
```json
{
    "code": "0000000",
    "message": "请求成功",
    "data": {
        "session_id": "session_abc123def456",
        "answer": "向量数据库是一种专门用于存储和查询向量数据的数据库系统...",
        "is_tool_call": false,
        "tool_name": null,
        "tool_params": null,
        "tool_result": null,
        "timestamp": "2024-01-01T12:00:01"
    }
}
```

**响应（有工具调用）：**
```json
{
    "code": "0000000",
    "message": "请求成功",
    "data": {
        "session_id": "session_abc123def456",
        "answer": "向量数据库是一种专门用于存储和查询向量数据的数据库系统...",
        "is_tool_call": true,
        "tool_name": "rag_search",
        "tool_params": {
            "query": "什么是向量数据库？",
            "top_k": 10
        },
        "tool_result": "检索到以下相关信息：...",
        "timestamp": "2024-01-01T12:00:01"
    }
}
```

#### 2.3 获取会话历史
```http
GET /v1/agent/session/{session_id}/history
```

**响应：**
```json
{
    "code": "0000000",
    "message": "获取成功",
    "data": {
        "session_id": "session_abc123def456",
        "messages": [
            {
                "role": "system",
                "content": "你是一个智能助手...",
                "timestamp": "2024-01-01T12:00:00"
            },
            {
                "role": "user",
                "content": "什么是向量数据库？",
                "timestamp": "2024-01-01T12:00:01"
            },
            {
                "role": "assistant",
                "content": "向量数据库是...",
                "timestamp": "2024-01-01T12:00:02"
            }
        ],
        "created_at": "2024-01-01T12:00:00",
        "updated_at": "2024-01-01T12:00:02"
    }
}
```

#### 2.4 删除会话
```http
DELETE /v1/agent/session/{session_id}
```

**响应：**
```json
{
    "code": "0000000",
    "message": "会话删除成功",
    "data": null
}
```

## Python SDK 使用示例
```python
import requests

BASE_URL = "http://localhost:8000/v1"

# 1. 创建会话
session_response = requests.post(
    f"{BASE_URL}/agent/session",
    json={"user_id": "test_user"}
)
session_id = session_response.json()["data"]["session_id"]
print(f"创建会话成功: {session_id}")

# 2. 发送消息
chat_response = requests.post(
    f"{BASE_URL}/agent/chat",
    json={
        "session_id": session_id,
        "message": "什么是向量数据库？"
    }
)
result = chat_response.json()["data"]
print(f"回答: {result['answer']}")
print(f"是否调用工具: {result['is_tool_call']}")
if result['is_tool_call']:
    print(f"调用工具: {result['tool_name']}")
    print(f"工具参数: {result['tool_params']}")

# 3. 多轮对话
second_chat_response = requests.post(
    f"{BASE_URL}/agent/chat",
    json={
        "session_id": session_id,
        "message": "它有什么优势？"
    }
)
second_result = second_chat_response.json()["data"]
print(f"\n第二个问题回答: {second_result['answer']}")

# 4. 获取历史记录
history_response = requests.get(
    f"{BASE_URL}/agent/session/{session_id}/history"
)
history = history_response.json()["data"]
print(f"\n历史消息数: {len(history['messages'])}")

# 5. 删除会话
delete_response = requests.delete(
    f"{BASE_URL}/agent/session/{session_id}"
)
print(f"\n删除会话: {delete_response.json()['message']}")
```

## 系统架构
```
backend/v1/app/agent/
├── __init__.py              # 模块导出
├── config.py                # 配置文件
├── core/                    # 核心层
│   ├── agent.py             # Agent核心逻辑，处理对话和工具调用
│   └── context.py           # 会话上下文管理
├── tools/                   # 工具层
│   ├── base.py              # 工具抽象基类
│   └── rag_tool.py          # RAG检索工具实现
├── service/                 # 服务层
│   └── agent_service.py     # 统一服务接口
├── controller/              # Controller层
│   └── agent_controller.py  # HTTP API接口
├── dto/                     # 数据传输对象
│   ├── request.py           # 请求DTO
│   └── response.py          # 响应DTO
└── README.md                # 使用文档
```

## 扩展开发：添加新工具
### 步骤1：实现工具类
在`tools/`目录下创建新的工具类，继承`BaseTool`：
```python
from typing import Dict, Any
from .base import BaseTool

class CalculatorTool(BaseTool):
    """计算器工具，用于数学计算"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "进行数学计算，当需要解决数学问题时使用此工具。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如'2 + 3 * 4'"
                }
            },
            "required": ["expression"]
        }

    def execute(self, params: Dict[str, Any]) -> str:
        expression = params.get("expression", "")
        try:
            # 安全计算，实际场景需要更安全的实现
            result = eval(expression)
            return f"计算结果: {result}"
        except Exception as e:
            return f"计算错误: {str(e)}"
```

### 步骤2：注册工具
在`config.py`中添加工具配置：
```python
# 工具定义映射
TOOL_CLASS_MAPPING: Dict[str, str] = {
    "rag_search": "backend.v1.app.agent.tools.rag_tool.RAGSearchTool",
    "calculator": "backend.v1.app.agent.tools.calculator_tool.CalculatorTool",  # 新增
}

# Agent配置
AGENT_CONFIG: Dict[str, Any] = {
    "tools": {
        "enabled": ["rag_search", "calculator"],  # 添加到启用列表
        # ...其他配置
    }
}
```

完成后Agent就可以自动识别并使用新添加的计算器工具了。

## 配置说明
主要配置在`config.py`文件中：
- `model`：大模型参数配置（模型名称、温度、最大token等）
- `tools`：工具配置（启用的工具列表、各工具参数）
- `session`：会话配置（超时时间、最大历史长度等）
- `system_prompt`：Agent系统提示词，可根据业务场景自定义

## 注意事项
1. 会话默认超时时间为1小时，超时后会自动清理
2. 工具调用目前只支持单轮调用，后续会支持多轮工具调用
3. 会话存储目前使用内存存储，分布式部署时建议扩展为Redis等持久化存储
4. 大模型工具调用的准确性依赖于提示词和工具描述的准确性
