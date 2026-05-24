# 视频生成功能模块 Spec 文档

## 1. 模块概述

本模块负责VidMuse项目中的视频生成完整流程，包括：剧本生成、TTS配音、场景配图、视频合成等核心功能。

### 1.1 职责范围
- 位于 `backend/v1/app/generate/` 目录
- 负责编排整个视频生成pipeline
- 调用搭档提供的AI接口和对象存储服务

---

## 2. 现有接口和函数验证

### 2.1 对象存储服务 ✅ 已就绪

**MinIO客户端** (`backend/store/obj/minio_client.py`)
- `upload_file(file_path, object_name, content_type)` - 上传本地文件
- `upload_fileobj(file, object_name, content_type)` - 上传文件对象
- `get_presigned_url(object_name, expires_in)` - 获取预签名URL
- `download_file(object_name, file_path)` - 下载文件
- `get_object(object_name)` - 获取对象内容
- `delete_object(object_name)` - 删除对象
- `object_exists(object_name)` - 检查对象是否存在

**TOS客户端** (`backend/store/obj/tos_client.py`)
- 同MinIO接口，火山引擎对象存储实现
- 支持配置切换（`settings.STORAGE_TYPE`）

**状态**: ✅ 可用，已实现完整CRUD操作

---

### 2.2 AI接口服务 ✅ 已就绪

**火山引擎LLM** (`backend/providers/volcano.py`)

| 方法 | 功能 | 状态 |
|------|------|------|
| `_chat(request)` | 对话接口 | ✅ 可用 |
| `_stream_chat(request)` | 流式对话 | ✅ 可用 |
| `generate_video(request, prompt, image)` | 视频生成（Seedance 1.5） | ✅ 可用 |
| `_embedding(request)` | 文本嵌入 | ✅ 可用 |
| `image_understanding(request)` | 图片理解 | ✅ 可用 |
| `text_understanding(request)` | 文本理解 | ✅ 可用 |
| `video_understanding(request)` | 视频理解 | ✅ 可用 |

**DTO定义** (`backend/providers/dto/schema.py`)
- `ChatRequest/ChatResponse` - 对话请求响应
- `VideoRequest/VideoResponse` - 视频生成请求响应
- `ImageUnderstandingRequest/Response` - 图片理解
- `TextUnderstandingRequest/Response` - 文本理解
- `EmbeddingRequest/EmbeddingResponse` - 嵌入向量

**状态**: ✅ 可用，接口定义完善

---

### 2.3 数据库模型 ✅ 已就绪

| 模型 | 表名 | 主要字段 | 状态 |
|------|------|----------|------|
| `Project` | projects | id, title, description, product_info, video_output_url, status | ✅ |
| `Script` | scripts | id, project_id, content(JSON), target_duration, ai_model | ✅ |
| `Material` | materials | id, project_id, script_id, type, url, duration, scene_index | ✅ |

**状态流转**: `draft` → `script_ready` → `processing` → `completed`/`failed`

---

### 2.4 异步任务框架 ✅ 已就绪

**Celery配置** (`backend/v1/app/generate/temp/celery_app.py`)
- Broker: Redis
- 任务超时: 软限制10分钟，硬限制15分钟
- 已配置任务重试机制

**状态**: ✅ 框架可用，需要实现具体业务逻辑

---

## 3. 当前Mock实现分析

### 3.1 剧本生成服务 (`script_generation.py`)

**当前状态**: Mock实现

**需要修改**:
- 接入火山引擎 `text_understanding()` 或 `_chat()` 接口
- 使用 `_build_prompt()` 构造的提示词调用LLM
- 解析LLM返回的JSON格式剧本

**修改范围**: 仅修改 `ScriptGenerationService` 类内部实现

---

### 3.2 TTS服务 (`tts_service.py`)

**当前状态**: Mock实现（生成静音音频）

**需要修改**:
- 接入火山引擎TTS API 或其他TTS服务
- 支持多种音色（voice_type参数）
- 返回真实音频文件路径

**可选方案**:
1. 火山引擎语音合成API
2. Azure Speech Services
3. 其他第三方TTS

**修改范围**: 仅修改 `TtsService` 类内部实现

---

### 3.3 图片服务 (`image_service.py`)

**当前状态**: Mock实现（生成占位PNG）

**需要修改**:
- 方案A: 调用AI图片生成API（如火山引擎图片生成）
- 方案B: 根据关键词搜索素材库
- 方案C: 混合方案（优先搜索，无结果时生成）

**修改范围**: 仅修改 `ImageService` 类内部实现

---

### 3.4 视频合成服务 (`video_composer.py`)

**当前状态**: Mock实现（生成空文件）

**需要修改**:
- 使用 `ffmpeg` 或 `moviepy` 进行真实视频合成
- 合成逻辑：图片序列 + 音频 + 字幕 → MP4
- 支持转场效果（可选）

**依赖**: 需要安装ffmpeg/moviepy

**修改范围**: 仅修改 `VideoComposer` 类内部实现

---

## 4. 发现的问题

### 4.1 minio_service 引用缺失 ⚠️

**问题位置**: `video_tasks.py` 第17行
```python
from backend.v1.app.services.minio_service import minio_service
```

**问题**: 该模块不存在于当前代码库中

**解决方案**:
1. 创建 `backend/v1/app/services/minio_service.py` 封装存储操作
2. 或者直接使用 `backend/store/obj/` 中的客户端

**建议**: 创建service层封装，统一存储操作接口

---

## 5. 实施方案

### 5.1 修改策略

遵循最小化修改原则，仅在 `generate/` 目录内进行修改，不改变现有文件架构。

### 5.2 实施步骤

#### Step 1: 创建minio_service封装
**新建文件**: `backend/v1/app/services/minio_service.py`

```python
"""存储服务封装"""
from backend.store.obj.factory import get_storage_client

class MinioService:
    def __init__(self):
        self.client = get_storage_client()

    def upload_file(self, file_path: str, object_name: str) -> str:
        return self.client.upload_file(file_path, object_name)

    def get_url(self, object_name: str) -> str:
        return self.client.get_presigned_url(object_name)

minio_service = MinioService()
```

---

#### Step 2: 修改剧本生成服务
**修改文件**: `backend/v1/app/generate/service/script_generation.py`

**修改内容**:
- 导入火山引擎provider
- 在 `generate_script()` 中调用真实LLM
- 添加JSON解析和错误处理
- 保留 `_mock_generate()` 作为fallback

---

#### Step 3: 修改TTS服务
**修改文件**: `backend/v1/app/generate/service/tts_service.py`

**修改内容**:
- 集成火山引擎TTS API（或选定的TTS服务）
- 实现 `generate_audio()` 真实调用
- 添加音频文件验证

---

#### Step 4: 修改图片服务
**修改文件**: `backend/v1/app/generate/service/image_service.py`

**修改内容**:
- 集成图片生成API或素材搜索
- 实现 `prepare_scene_images()` 真实调用
- 添加图片下载和本地缓存

---

#### Step 5: 修改视频合成服务
**修改文件**: `backend/v1/app/generate/service/video_composer.py`

**修改内容**:
- 集成moviepy/ffmpeg
- 实现图片+音频+字幕合成
- 添加转场效果（可选）

---

## 6. 接口调用关系图

```
前端请求
    │
    ▼
[Controller] generation.py
    │
    ├─→ [ScriptGenerationService] ──→ VolcanoLLM.text_understanding()
    │
    └─→ [VideoGenerationService] ──→ Celery Task
                                        │
                                        ▼
                              [generate_video_task]
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            [TtsService]        [ImageService]      [VideoComposer]
                    │                   │                   │
                    ▼                   ▼                   ▼
            TTS API / 素材库      图片API / 搜索      moviepy/ffmpeg
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                              [MinioService] ──→ TOS/MinIO
                                        │
                                        ▼
                              更新数据库状态
```

---

## 7. 环境依赖

### 7.1 Python包依赖
```txt
# 现有依赖（已在项目中）
sqlalchemy
fastapi
celery
redis
pydantic

# 新增依赖（视频合成）
moviepy>=1.0.3
# 或
ffmpeg-python>=0.2.0

# TTS依赖（根据选择的TTS服务）
# volcano-tts-sdk 或其他
```

### 7.2 环境变量
```env
# 已配置
DOUBAO_SEED_API_KEY=xxx
TOS_ACCESS_KEY=xxx
TOS_SECRET_KEY=xxx

# 可能需要新增
TTS_API_KEY=xxx
TTS_SERVICE=volcano  # 或 azure, aliyun 等
IMAGE_GEN_API_KEY=xxx
```

---

## 8. 测试计划

### 8.1 单元测试
- 各Service方法的Mock测试
- JSON解析测试
- 错误处理测试
测试用例写在tests/turlin里面

### 8.2 集成测试
- 端到端视频生成流程测试
- Celery任务执行测试
- 存储上传下载测试

### 8.3 测试用例
```python
# 示例测试用例
async def test_script_generation():
    """测试剧本生成"""
    service = ScriptGenerationService()
    script = await service.generate_script(db, project_id=1, target_duration=30)
    assert script.content is not None
    content = json.loads(script.content)
    assert "body" in content
    assert len(content["body"]) > 0
```

---

## 9. 风险和注意事项

### 9.1 技术风险
- **TTS API限制**: 可能有并发数或字符数限制
- **视频合成耗时**: 长视频合成可能超时，需要合理设置Celery超时
- **存储空间**: 生成的素材文件较大，注意存储配额

### 9.2 注意事项
- 保持现有的Mock方法作为fallback
- 添加充分的日志记录
- 处理好异步/同步转换（Celery worker中使用同步）
- 文件路径使用临时目录，任务完成后清理

---

## 10. 完成标准

- [ ] 剧本生成调用真实LLM接口
- [ ] TTS服务生成真实音频
- [ ] 图片服务获取真实配图
- [ ] 视频合成生成可播放MP4
- [ ] 所有素材上传到对象存储
- [ ] 数据库状态正确流转
- [ ] 错误处理和日志完善
- [ ] 单元测试通过

---

## 11. 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/v1/app/services/minio_service.py` | 新建 | 存储服务封装 |
| `backend/v1/app/generate/service/script_generation.py` | 修改 | 接入LLM |
| `backend/v1/app/generate/service/tts_service.py` | 修改 | 接入TTS |
| `backend/v1/app/generate/service/image_service.py` | 修改 | 接入图片API |
| `backend/v1/app/generate/service/video_composer.py` | 修改 | 真实视频合成 |
| `requirements.txt` | 修改 | 添加moviepy依赖 |

**注意**: 不修改现有模型、控制器、配置等文件
