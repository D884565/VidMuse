---
name: video-parsing-pipeline
description: 视频解析流水线设计文档，实现视频拆分、大模型理解、JSON生成、结构校验的完整处理流程
metadata:
  type: design
  version: 1.0
  date: 2026-05-25
  author: Claude
---

# 视频解析流水线设计文档

## 1. 概述
本设计实现了可扩展的流水线架构，用于处理视频解析任务。视频解析流水线是三条流水线中的第一条，主要功能是将长视频拆分为多个短视频片段，通过大模型理解片段内容，生成符合格式要求的JSON文件，并进行结构校验。

## 2. 架构设计
采用插件化流水线架构，核心由三部分组成：
- **处理器(Processor)**：单个处理步骤的抽象，实现具体的业务逻辑
- **上下文(Context)**：在处理器之间传递数据的载体
- **流水线(Pipeline)**：多个处理器的有序组合，执行完整的处理流程

### 2.1 核心抽象层

#### 2.1.1 Processor 接口
所有处理步骤必须实现的抽象基类：
```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseProcessor(ABC):
    """处理器抽象基类"""
    
    @abstractmethod
    def process(self, context: "PipelineContext") -> "PipelineContext":
        """
        处理上下文数据并返回修改后的上下文
        
        :param context: 流水线上下文对象
        :return: 修改后的上下文对象
        """
        pass
```

#### 2.1.2 PipelineContext 上下文
用于在处理器之间传递数据和状态：
```python
from typing import Any, Dict, List, Optional

class PipelineContext:
    """流水线上下文，用于在处理器之间传递数据"""
    
    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self.data: Dict[str, Any] = initial_data or {}  # 业务数据
        self.errors: List[Exception] = []  # 错误信息
        self.metadata: Dict[str, Any] = {}  # 元数据/临时存储
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取数据"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置数据"""
        self.data[key] = value
    
    def add_error(self, error: Exception) -> None:
        """添加错误信息"""
        self.errors.append(error)
    
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0
```

#### 2.1.3 BasePipeline 流水线抽象
所有流水线的基类：
```python
from typing import List, Dict, Any
from .processor import BaseProcessor
from .context import PipelineContext

class BasePipeline(ABC):
    """流水线抽象基类"""
    
    def __init__(self, processors: List[BaseProcessor]):
        self.processors = processors  # 处理器列表，按顺序执行
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行完整的流水线
        
        :param input_data: 输入数据
        :return: 处理结果
        """
        context = PipelineContext(input_data)
        
        for processor in self.processors:
            if context.has_errors():
                break  # 有错误时终止执行
            context = processor.process(context)
        
        return self._build_result(context)
    
    def _build_result(self, context: PipelineContext) -> Dict[str, Any]:
        """构建最终返回结果"""
        return {
            "success": not context.has_errors(),
            "data": context.data,
            "errors": [str(e) for e in context.errors],
            "metadata": context.metadata
        }
```

## 3. 视频解析流水线实现

### 3.1 流水线组成
视频解析流水线由以下4个处理器按顺序组成：

1. **VideoSplitProcessor**：视频拆分处理器
2. **VideoUnderstandingProcessor**：视频理解处理器
3. **SliceGenerateProcessor**：切片JSON生成处理器
4. **SchemaValidationProcessor**：结构校验处理器

### 3.2 各处理器详细设计

#### 3.2.1 VideoSplitProcessor 视频拆分处理器
**功能**：将长视频拆分为多个短视频片段
- **输入**：`video_id`(视频ID), `video_path`(视频文件路径)
- **输出**：`slices: List[Dict]` 视频片段列表，每个元素包含：
  - `slice_id`: 片段唯一标识（格式：s_001）
  - `time_range`: 时间范围 [开始毫秒, 结束毫秒]
  - `video_id`: 所属视频ID
- **实现**：mock拆分逻辑，按固定时长（例如5秒）切分视频

#### 3.2.2 VideoUnderstandingProcessor 视频理解处理器
**功能**：调用provider包下的大模型接口分析每个视频片段的内容
- **输入**：`slices: List[Dict]` 视频片段列表
- **处理**：并行调用大模型接口分析每个片段的内容
- **输出**：`understood_slices: List[Dict]` 包含理解结果的片段列表，每个元素新增：
  - `understanding`: 大模型返回的理解结果
  - `raw_response`: 大模型原始响应（可选）

#### 3.2.3 SliceGenerateProcessor 切片JSON生成处理器
**功能**：根据大模型理解结果，按照slice.json模板生成每个片段的JSON文件
- **输入**：`understood_slices: List[Dict]` 包含理解结果的片段列表
- **处理**：
  1. 按照slice.json模板结构整理数据
  2. 将每个片段保存为独立的JSON文件到resources/resolve目录
- **输出**：
  - `slice_files: List[str]` 生成的JSON文件路径列表
  - `slice_data: List[Dict]` 生成的切片数据列表

#### 3.2.4 SchemaValidationProcessor 结构校验处理器
**功能**：使用slice_valid.json的JSON Schema校验生成的JSON文件结构
- **输入**：`slice_data: List[Dict]` 生成的切片数据列表
- **处理**：
  1. 加载slice_valid.json的JSON Schema
  2. 逐个校验切片数据的结构合法性
- **输出**：
  - `valid_slices: List[Dict]` 校验通过的切片列表
  - `invalid_slices: List[Dict]` 校验失败的切片列表，包含错误信息
  - `validation_summary`: 校验统计信息（总数、通过数、失败数）

## 4. 数据流示例

```
输入: 
{
  "video_id": "v_001", 
  "video_path": "/data/videos/demo.mp4"
}

↓ VideoSplitProcessor 处理

{
  "video_id": "v_001",
  "video_path": "/data/videos/demo.mp4",
  "slices": [
    {"slice_id": "s_001", "time_range": [0, 5000], "video_id": "v_001"},
    {"slice_id": "s_002", "time_range": [5000, 10000], "video_id": "v_001"},
    ...
  ]
}

↓ VideoUnderstandingProcessor 处理

{
  ...
  "understood_slices": [
    {
      "slice_id": "s_001", 
      "time_range": [0, 5000], 
      "video_id": "v_001",
      "understanding": {
        "模板名称": "主播情绪开场",
        "模板类型": "HOOK",
        "创作要素": {
          "画面": "主播半身中景，明亮直播间，暖色调",
          "动作": "挥手打招呼，表情兴奋",
          "台词": "家人们，谁懂啊！",
          "运镜": "固定机位，平视角度",
          "时长": "3-5秒",
          "情绪评分": 0.8
        },
        "生成Prompt完整模板": "中景固定机位，年轻女性主播在明亮直播间兴奋挥手打招呼，暖色调布光，专业电商质感，高清"
      }
    },
    ...
  ]
}

↓ SliceGenerateProcessor 处理

{
  ...
  "slice_files": [
    "/resources/resolve/v_001_s_001.json",
    "/resources/resolve/v_001_s_002.json",
    ...
  ],
  "slice_data": [
    {
      "slice_id": "s_001",
      "time_range": [0, 5000],
      "video_id": "v_001",
      "单片段模板": {
        "模板名称": "主播情绪开场",
        "模板类型": "HOOK",
        "创作要素": {
          "画面": "主播半身中景，明亮直播间，暖色调",
          "动作": "挥手打招呼，表情兴奋",
          "台词": "家人们，谁懂啊！",
          "运镜": "固定机位，平视角度",
          "时长": "3-5秒",
          "情绪评分": 0.8
        },
        "生成Prompt完整模板": "中景固定机位，年轻女性主播在明亮直播间兴奋挥手打招呼，暖色调布光，专业电商质感，高清"
      }
    },
    ...
  ]
}

↓ SchemaValidationProcessor 处理

{
  "success": true,
  "data": {
    ...
    "valid_slices": [...],
    "invalid_slices": [],
    "validation_summary": {
      "total": 10,
      "valid": 10,
      "invalid": 0
    }
  },
  "errors": [],
  "metadata": {}
}
```

## 5. 扩展性设计

### 5.1 新增流水线
后续添加另外两条流水线只需要：
1. 实现特定的Processor类
2. 组装成新的Pipeline子类即可
3. 现有处理器可以在不同流水线之间复用

### 5.2 扩展处理器
可以很方便地添加新的处理器，例如：
- 内容质量校验处理器
- 重复内容去重处理器
- 标签生成处理器
- 数据落库处理器等

### 5.3 全局扩展
支持在流水线层面添加全局中间件：
- 日志监控
- 性能统计
- 限流降级
- 权限控制等

## 6. 目录结构

```
backend/v1/app/rag/core/pipline/
├── __init__.py                  # 导出公共接口
├── base/                        # 核心抽象层
│   ├── __init__.py
│   ├── processor.py            # BaseProcessor 定义
│   ├── context.py              # PipelineContext 定义
│   └── pipeline.py             # BasePipeline 定义
├── processors/                  # 具体处理器实现
│   ├── __init__.py
│   ├── video_split_processor.py
│   ├── video_understanding_processor.py
│   ├── slice_generate_processor.py
│   └── schema_validation_processor.py
└── pipelines/                   # 具体流水线实现
    ├── __init__.py
    └── video_parsing_pipeline.py
```

## 7. 使用示例

```python
from backend.v1.app.rag.core.pipline.pipelines.video_parsing_pipeline import VideoParsingPipeline

# 创建流水线实例
pipeline = VideoParsingPipeline()

# 执行流水线
result = pipeline.run({
    "video_id": "v_001",
    "video_path": "/path/to/video.mp4"
})

# 处理结果
if result["success"]:
    print(f"处理成功，生成{len(result['data']['valid_slices'])}个有效切片")
else:
    print(f"处理失败：{result['errors']}")
```
