# Agent模块使用文档

## 概述
本模块实现了基于ReAct范式的多Agent系统，支持记忆、工具调用、私有资产管理和上下文构建等核心功能。

## 快速开始

### 1. 创建Agent实例
```python
from backend.v1.app.agent import ReActAgent

# 创建Agent
agent = ReActAgent(
    agent_id="my_agent_001",
    name="我的智能助手",
    description="这是一个通用的智能助手，可以回答问题和执行工具调用。"
)
```

### 2. 注册工具
```python
from backend.v1.app.agent import BaseTool, register_tool
from typing import Dict, Any

# 自定义工具
@register_tool
class WeatherTool(BaseTool):
    name = "get_weather"
    description = "获取指定城市的天气信息"
    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称"}
        },
        "required": ["city"]
    }
    
    def execute(self, parameters: Dict[str, Any]) -> str:
        city = parameters["city"]
        return f"{city}今天天气晴朗，温度25°C。"

# 注册工具到Agent
agent.tool_system.register_tool(WeatherTool())
```

### 3. 运行Agent
```python
# 直接提问（不需要工具）
result = agent.run("你好，介绍一下你自己")
print(result["answer"])

# 需要调用工具的问题
result = agent.run("北京今天天气怎么样？")
print(result["answer"])
```

### 4. 使用私有资产
```python
# 保存资产
agent.asset_store.save("user_preferences", {
    "theme": "dark",
    "language": "zh-CN",
    "notifications": True
})

# 加载资产
preferences = agent.asset_store.load("user_preferences")
print(f"用户主题: {preferences['theme']}")
```

### 5. 使用记忆系统
```python
# 添加自定义记忆
agent.memory.add("用户喜欢Python编程语言", {"type": "user_preference"})

# 搜索记忆
related_memories = agent.memory.search("Python")
print(f"找到{len(related_memories)}条相关记忆")
```

## 扩展自定义Agent
```python
from backend.v1.app.agent import ReActAgent

class CustomAgent(ReActAgent):
    """自定义业务Agent"""
    
    def __init__(self, agent_id: str, name: str, **kwargs):
        super().__init__(agent_id, name, **kwargs)
        
        # 自定义初始化逻辑
        self._load_custom_tools()
        self._load_custom_config()
    
    def _load_custom_tools(self):
        """加载业务专用工具"""
        from my_tools import BusinessTool1, BusinessTool2
        self.tool_system.register_tool(BusinessTool1())
        self.tool_system.register_tool(BusinessTool2())
    
    def _load_custom_config(self):
        """加载自定义配置"""
        config = self.asset_store.load("custom_config", {})
        self.model_config["temperature"] = config.get("temperature", 0.7)
```

## 核心组件说明

| 组件 | 说明 |
|------|------|
| ReActAgent | 基于ReAct范式的Agent实现，提供核心执行逻辑 |
| ShortTermMemory | 短期记忆，存储会话历史，内存存储 |
| LongTermMemory | 长期记忆，持久化存储，支持向量检索 |
| ToolSystem | 工具管理系统，支持工具的注册和执行 |
| LocalAssetStore | 本地资产存储，每个Agent独立的存储空间 |
| PromptBuilder | Prompt构建器，支持动态上下文生成 |

## 配置说明
配置文件位于 `backend/v1/app/agent/config.py`，可以通过环境变量覆盖默认配置：
- `DOUBAO_SEED_API_KEY`: 豆包API密钥
- `DOUBAO_SEED`: 默认使用的模型
- `EMBEDDING_MODEL`: 向量嵌入模型

## 最佳实践
1. 每个业务Agent使用独立的agent_id，避免资产和记忆混淆
2. 工具设计要遵循单一职责原则，每个工具只做一件事
3. 敏感信息不要保存在记忆或资产中，使用环境变量存储
4. 对于复杂任务，合理设置max_iterations，避免无限循环
5. 定期清理过期的会话记忆和不需要的资产
