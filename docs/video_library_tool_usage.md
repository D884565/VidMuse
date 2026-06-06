# 视频库查询工具使用说明

## 工具简介
`VideoLibraryQueryTool` 是一个可以被Agent调用的工具，用于根据商品分类信息查询视频素材库中的相关视频。

## 功能特性
- 支持按分类名称查询
- 支持按分类ID查询（优先级更高）
- 支持按最低热度分数过滤
- 返回视频的详细信息，包括标题、描述、URL、热度等

## 工具定义
```json
{
  "name": "query_video_library",
  "description": "根据商品分类信息查询视频素材库中的相关视频，返回视频的标题、描述、URL、热度等信息",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "商品分类名称，例如：'手机', '电脑', '服装'等"
      },
      "category_id": {
        "type": "integer",
        "description": "商品分类ID，优先级高于category名称"
      },
      "min_hot_score": {
        "type": "integer",
        "description": "最低热度分数，返回热度大于等于该值的视频，默认80",
        "default": 80
      },
      "limit": {
        "type": "integer",
        "description": "返回结果数量，默认返回10条",
        "default": 10
      }
    },
    "required": []
  }
}
```

## 使用示例

### 1. 直接调用工具
```python
from backend.v1.app.agent.tools import VideoLibraryQueryTool

# 创建工具实例
tool = VideoLibraryQueryTool()

# 按分类名称查询
result = tool.execute({
    "category": "手机",
    "min_hot_score": 85,
    "limit": 5
})
print(result)

# 按分类ID查询
result = tool.execute({
    "category_id": 123,
    "limit": 10
})
print(result)
```

### 2. 在Agent中使用
```python
from backend.v1.app.agent.implementations.react_agent import ReActAgent
from backend.v1.app.agent.implementations.tool_system import ToolSystem

# 创建工具系统，会自动注册所有已注册的工具
tool_system = ToolSystem()

# 创建Agent
agent = ReActAgent(
    tool_system=tool_system,
    # 其他配置...
)

# Agent会根据用户查询自动决定是否调用该工具
response = await agent.chat("帮我找一些关于手机的爆款视频")
```

### 3. 返回结果格式
```json
{
  "total": 25,
  "count": 5,
  "videos": [
    {
      "video_id": 1,
      "title": "最新款手机测评",
      "description": "这是一款非常棒的手机...",
      "url": "https://example.com/video/1.mp4",
      "cover_url": "https://example.com/cover/1.jpg",
      "duration": 120,
      "hot_score": 92,
      "category": "手机",
      "tags": ["手机", "测评", "数码"],
      "source_type": 1,
      "created_at": "2024-01-01 12:00:00"
    }
  ]
}
```

### 4. 错误返回格式
```json
{
  "error": "参数错误",
  "message": "必须提供category或category_id至少一个参数"
}
```

## 注意事项
1. 必须提供 `category` 或 `category_id` 至少一个参数
2. `category_id` 的优先级高于 `category`
3. 热度分数范围通常是0-100，默认返回80分以上的视频
4. 返回结果默认按热度从高到低排序
5. 工具内部会处理数据库连接和异常，不会抛出异常，所有错误都以JSON格式返回
