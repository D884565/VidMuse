# vidmuse/provider 模块分析与联调方案

## 一、模块概述

`backend/vidmuse/provider` 是搭档开发的 **LLM 服务封装层**，基于火山引擎（豆包/Ark SDK）实现了统一的 AI 能力接口。当前该模块与 `backend/app` 业务层**完全未对接**。

```
backend/vidmuse/
├── __init__.py
└── provider/
    ├── __init__.py          # 统一导出入口（18 个符号）
    ├── base.py              # LLM 抽象基类 + 流式回调接口
    ├── volcano.py           # 火山引擎 VolcanoLLM 实现
    └── dto/
        └── schema.py        # 15 个 Pydantic DTO 定义
```

---

## 二、提供的能力清单

### 2.1 基类接口（LLMBase）

| 方法 | 签名 | 说明 |
|---|---|---|
| `chat` | `(request: ChatRequest) -> ChatResponse` | 同步对话 |
| `stream_chat` | `(request: ChatRequest) -> Iterator[str]` | 流式对话 |
| `stream_chat_with_callback` | `(request: ChatRequest, callback: StreamChatCallback) -> None` | 回调式流式对话 |
| `embedding` | `(request: EmbeddingRequest) -> EmbeddingResponse` | 文本嵌入 |

设计模式：模板方法模式。公开方法统一处理异常，具体实现委托给抽象方法 `_chat` / `_stream_chat` / `_embedding`。

### 2.2 VolcanoLLM 扩展方法（不在基类中）

| 方法 | 签名 | 说明 |
|---|---|---|
| `generate_video` | `async (request: VideoRequest, prompt: str, image: str \| None) -> VideoResponse \| None` | 视频生成（Seedance 1.5），含轮询逻辑，最长 5 分钟 |
| `image_understanding` | `(request: ImageUnderstandingRequest) -> ImageUnderstandingResponse` | 多模态图片理解 |
| `text_understanding` | `(request: TextUnderstandingRequest) -> TextUnderstandingResponse` | 文本理解 |
| `video_understanding` | `async (request: VideoUnderstandingRequest) -> VideoUnderstandingResponse` | 多模态视频理解 |

### 2.3 DTO 数据结构

| 分组 | 类 | 用途 |
|---|---|---|
| 对话 | `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatUsage` | LLM 对话交互 |
| 嵌入 | `EmbeddingRequest`, `EmbeddingResponse`, `EmbeddingUsage` | 文本向量化 |
| 视频生成 | `VideoRequest`, `VideoResponse` | AI 视频生成 |
| 图片理解 | `ImageUnderstandingRequest`, `ImageUnderstandingResponse` | 图片内容分析 |
| 视频理解 | `VideoUnderstandingRequest`, `VideoUnderstandingResponse` | 视频内容分析 |
| 文本理解 | `TextUnderstandingRequest`, `TextUnderstandingResponse` | 文本内容分析 |

---

## 三、当前断裂点

```
vidmuse/provider/                      app/
┌─────────────────────┐                ┌──────────────────────────────┐
│ LLMBase (abstract)  │                │ ScriptGenerationService      │
│  ├─ chat()          │                │  └─ _mock_generate()  ◄── 未接入LLM │
│  ├─ stream_chat()   │                │                              │
│  ├─ stream_chat_    │  ◄── 零调用 ── │ TtsService                   │
│  │   with_callback()│                │  └─ _create_silent_audio()   │
│  └─ embedding()     │                │                              │
│                     │                │ ImageService                 │
│ VolcanoLLM          │                │  └─ _create_placeholder_png()│
│  ├─ _chat()         │                │                              │
│  ├─ _stream_chat()  │                │ video_tasks.py (Celery)      │
│  ├─ _embedding()    │                │  └─ 顺序编排 Mock 服务       │
│  ├─ generate_video()│                │                              │
│  ├─ image_          │                │ config.py                    │
│  │  understanding() │                │  └─ OPENAI_API_KEY (空)      │
│  ├─ text_           │                │    (无火山引擎配置)           │
│  │  understanding() │                └──────────────────────────────┘
│  └─ video_
│     understanding() │
└─────────────────────┘
```

**断裂原因**：
- `app` 层服务全部使用 Mock 实现，未导入任何 `vidmuse.provider` 中的类
- `app/core/config.py` 无火山引擎配置项（API Key、模型名称）
- `vidmuse` 通过 `dotenv` 直接读取环境变量，与 `app` 的 Pydantic Settings 配置体系未统一

---

## 四、联调方案

### 4.1 剧本生成接入（app → vidmuse）

**改造文件**：`app/services/script_generation.py`

```python
# 当前：Mock 实现
def _mock_generate(self, ...):
    return Script(content={...})

# 改造后：调用 VolcanoLLM
from backend.vidmuse.provider import VolcanoLLM, ChatRequest, ChatMessage

class ScriptGenerationService:
    def __init__(self, llm: VolcanoLLM):
        self.llm = llm

    async def generate_script(self, project_id, target_duration, ...):
        prompt = self._build_prompt(product_info, knowledge, target_duration)
        request = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.7,
            max_tokens=2048,
        )
        response = self.llm.chat(request)
        script_content = self._parse_response(response.content)
        # 保存到 MySQL ...
```

**对应 spec 阶段**：阶段一（剧本生成真实化）

### 4.2 素材 AI 分析接入（app → vidmuse）

**改造文件**：`app/services/material_analysis.py`（新建）

```python
from backend.vidmuse.provider import VolcanoLLM, ImageUnderstandingRequest

class MaterialAnalysisService:
    def __init__(self, llm: VolcanoLLM):
        self.llm = llm

    def extract_features(self, image_url: str) -> dict:
        request = ImageUnderstandingRequest(
            image_url=image_url,
            prompt="请分析这张图片的内容、风格、颜色、物体，以JSON格式返回"
        )
        response = self.llm.image_understanding(request)
        return json.loads(response.content)

    def generate_embedding(self, texts: list[str]) -> list[list[float]]:
        request = EmbeddingRequest(texts=texts)
        response = self.llm.embedding(request)
        return response.embeddings
```

**对应 spec 阶段**：阶段六（ChromaDB 向量检索）

### 4.3 视频生成接入（app → vidmuse）

**改造文件**：`app/workers/video_tasks.py`

```python
from backend.vidmuse.provider import VolcanoLLM, VideoRequest

@celery_app.task(bind=True)
def generate_video_task(self, project_id, script_id):
    # Step 1: TTS（仍需独立 TTS 服务，vidmuse 未提供）
    audio_url = tts_service.generate_audio(full_text)

    # Step 2: 场景配图（可用 vidmuse image_understanding 分析，但生成需另接）
    images = image_service.prepare_scene_images(script_content)

    # Step 3: AI 视频生成（替代 FFmpeg 合成）
    video_response = await llm.generate_video(
        request=VideoRequest(ratio="9:16", duration=30),
        prompt=script_content["full_text"],
        image=images[0] if images else None,
    )
    # video_response.video_url 即为成品视频
```

**注意**：`generate_video` 是异步方法，Celery Worker 中调用需要 `asyncio.run()` 或改造为同步。

**对应 spec 阶段**：阶段三（视频合成真实化）的替代方案 — 用 AI 视频生成替代 FFmpeg 合成

### 4.4 配置统一

**改造文件**：`app/core/config.py`

```python
class Settings(BaseSettings):
    # 现有配置
    MYSQL_HOST: str = "localhost"
    REDIS_HOST: str = "localhost"
    # ...

    # 新增火山引擎配置
    DOUBAO_SEED_API_KEY: str = ""
    DOUBAO_SEED: str = "doubao-1.5-pro"
    DOUBAO_SEEDDANCE: str = "doubao-1.5-pro"
    VOLC_EMBEDDING_MODEL: str = "bge-large-zh"
```

**改造文件**：`app/core/dependencies.py`（新建）

```python
from backend.vidmuse.provider import VolcanoLLM
from app.core.config import settings

def get_llm() -> VolcanoLLM:
    return VolcanoLLM(
        key=settings.DOUBAO_SEED_API_KEY,
        model_name=settings.DOUBAO_SEED,
    )
```

---

## 五、能力覆盖对照表

| spec 需求 | vidmuse 能力 | 覆盖状态 | 说明 |
|---|---|---|---|
| 剧本生成（LLM 对话） | `chat()` / `stream_chat()` | **可直接使用** | 调用 `ChatRequest` 构造 Prompt |
| 商品信息解析 | `chat()` | **可直接使用** | 用简单 Prompt 解析商品文本 |
| 素材图片理解 | `image_understanding()` | **可直接使用** | 多模态分析图片内容 |
| 文本 Embedding | `embedding()` | **可直接使用** | 用于 RAG 向量化和语义检索 |
| AI 视频生成 | `generate_video()` | **可直接使用** | Seedance 1.5，替代 FFmpeg 合成 |
| 视频理解（参考视频分析） | `video_understanding()` | **可直接使用** | 用于 P2 仿写模式的视频拆解 |
| TTS 配音 | 无 | **需独立接入** | vidmuse 不包含 TTS，需对接火山引擎 TTS API 或 Edge TTS |
| 场景配图生成 | 无 | **需独立接入** | vidmuse 只有图片"理解"，无图片"生成"，需对接文生图 API |
| FFmpeg 视频合成 | 无 | **需独立实现** | 如不使用 AI 视频生成，仍需 FFmpeg 兜底方案 |

---

## 六、架构问题与建议

### 6.1 抽象基类缺口

`VolcanoLLM` 的 4 个扩展方法（`generate_video`、`image_understanding`、`text_understanding`、`video_understanding`）不在 `LLMBase` 基类中，未来切换 LLM 供应商时无法多态调用。

**建议**：与搭档协商，将这些能力提升到 `LLMBase` 抽象基类中。

### 6.2 同步/异步混用

`VolcanoLLM` 中 `chat`、`stream_chat`、`embedding`、`image_understanding`、`text_understanding` 是同步方法，而 `generate_video`、`video_understanding` 是异步方法。`app` 层 FastAPI 全部是异步。

**建议**：同步方法使用 `asyncio.to_thread()` 包装，或与搭档协商统一改为异步。

### 6.3 配置管理分裂

`vidmuse` 通过 `dotenv` 直接读取环境变量，`app` 使用 Pydantic Settings。两套体系未统一。

**建议**：将火山引擎配置项纳入 `app/core/config.py` 的 `Settings` 类，通过依赖注入传递给 `VolcanoLLM`。
