# Agentic RAG 系统使用文档

## 概述
Agentic RAG系统是一个基于大模型和工具调用的智能问答系统，能够自主决定何时检索知识库信息，何时直接回答用户问题。系统将意图识别、上下文管理、检索决策等能力全部交给大模型Agent自主处理，提供更智能、更准确的问答体验。

## 功能特性
- 🤖 **ReAct智能Agent**：基于思考-行动-观察范式，支持多轮推理和工具调用
- 🔧 **并行工具调用**：支持一次调用多个工具，提高复杂问题处理效率
- 🛠️ **多轮工具调用**：支持多次工具调用，逐步解决复杂问题
- 📚 **RAG集成**：无缝集成已有的RAG检索系统，获取知识库信息
- 💬 **多轮对话**：自动管理会话上下文，支持连贯的多轮对话
- 🧩 **可扩展架构**：插件式工具设计，新增工具无需修改核心代码
- 🚀 **内部调用接口**：提供简洁的Python接口，方便其他模块直接调用

## 快速开始

### 1. 环境配置
确保以下环境变量已配置（通常在项目根目录的.env文件中）：
```env
# 豆包API密钥
DOUBAO_SEED_API_KEY=your_api_key_here
```

### 2. 内部接口使用
系统提供简洁的Python接口，其他模块可以直接导入使用，无需通过HTTP调用。

#### 推荐方式：直接使用全局服务实例
```python
from backend.v1.app.agent import agent_service

# 方式一：快速聊天（自动管理会话，适合单轮查询）
answer = agent_service.quick_chat("什么是向量数据库？")
print(f"回答: {answer}")

# 方式二：管理会话（适合多轮对话）
# 1. 创建会话
session_id = agent_service.create_session(user_id="user_123", metadata={"platform": "internal"})
print(f"会话ID: {session_id}")

# 2. 多轮对话
response1 = agent_service.chat(session_id, "什么是向量数据库？")
print(f"问题1回答: {response1.answer}")
print(f"是否调用工具: {response1.is_tool_call}")

response2 = agent_service.chat(session_id, "它有什么优势？")
print(f"问题2回答: {response2.answer}")

# 3. 获取会话历史
messages = agent_service.get_session_history(session_id)
print(f"历史消息数: {len(messages)}")
for msg in messages:
    print(f"[{msg.role}]: {msg.content[:50]}...")

# 4. 删除会话
agent_service.delete_session(session_id)
```

#### 完整的接口说明
```python
# 创建会话
session_id = agent_service.create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str

# 发送消息聊天
response = agent_service.chat(
    session_id: str,
    message: str,
    tool_call_enabled: bool = True
) -> ChatResponse
# ChatResponse包含字段：
# - answer: str 回答内容
# - is_tool_call: bool 是否调用了工具
# - tool_name: Optional[str] 调用的工具名称（仅单工具调用时存在）
# - tool_params: Optional[Dict] 工具调用参数（仅单工具调用时存在）
# - tool_result: Optional[str] 工具返回结果（仅单工具调用时存在）
# - metadata: Optional[Dict] 额外元数据，包含：
#   - iterations: int 迭代次数
#   - tool_calls: List[Dict] 所有工具调用列表（多工具调用时可查看所有调用信息）
#   - tool_results: List[str] 所有工具返回结果列表
#   - max_iterations_reached: bool 是否达到最大迭代次数
# - session_id: str 会话ID
# - timestamp: datetime 响应时间

# 快速聊天（自动创建和销毁会话）
answer: str = agent_service.quick_chat(
    message: str,
    tool_call_enabled: bool = True
) -> str

# 获取会话历史
messages: Optional[List[Message]] = agent_service.get_session_history(
    session_id: str
)
# Message包含字段：
# - role: str 角色（user/assistant/system/tool）
# - content: str 内容
# - timestamp: datetime 时间戳
# - tool_call: Optional[Dict] 工具调用信息
# - tool_result: Optional[Dict] 工具结果信息

# 删除会话
success: bool = agent_service.delete_session(session_id: str)
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
