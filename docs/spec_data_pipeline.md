# 完整数据链路开发规格说明书

## 1. 链路总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AIGC 带货视频生成 - 完整数据链路                            │
│                                                                             │
│  用户输入商品信息                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ ① 素材准备   │───→│ ② 剧本生成   │───→│ ③ 视频生成   │───→│ ④ 输出交付   │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│       │                   │                   │                   │         │
│       ▼                   ▼                   ▼                   ▼         │
│  [图像理解模型]      [LLM文本生成]      [TTS/图像/视频模型]    [存储/分发]     │
│  [Embedding模型]     [Embedding模型]   [视频合成引擎]                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 完整链路步骤分解

### 步骤 ①：素材准备阶段

```
用户上传素材 ──→ MinIO存储 ──→ AI特征提取 ──→ 向量化入库
     │              │              │              │
   前端上传       存储服务      调用AI模型      ChromaDB
```

| 子步骤 | 动作 | 调用模型 | 输入 | 输出 | 存储位置 |
|---|---|---|---|---|---|
| 1.1 文件上传 | 用户上传图片/视频 | 无 | 原始文件 | MinIO路径 | MinIO |
| 1.2 图片理解 | 提取图片内容描述 | 多模态LLM (GPT-4V/Claude Vision) | 图片URL | 文字描述 | MySQL ai_features |
| 1.3 标签生成 | 生成素材标签 | LLM (GPT-3.5/Claude Haiku) | 图片描述 | 标签列表 | MySQL tags |
| 1.4 Embedding | 向量化存储 | Embedding模型 (text-embedding-3-small) | 文本描述 | 向量ID | ChromaDB |

---

### 步骤 ②：剧本生成阶段

```
商品信息 ──→ 知识检索(RAG) ──→ Prompt构造 ──→ LLM生成剧本 ──→ 解析入库
    │              │                │              │              │
 MySQL         ChromaDB          模板拼接      调用LLM        MySQL存储
```

| 子步骤 | 动作 | 调用模型 | 输入 | 输出 | 存储位置 |
|---|---|---|---|---|---|
| 2.1 读取商品信息 | 从MySQL获取项目信息 | 无 | project_id | 商品标题/信息 | - |
| 2.2 知识检索(RAG) | 检索相关商品知识 | Embedding模型 | 商品描述 | 知识片段列表 | ChromaDB |
| 2.3 素材检索 | 检索匹配素材 | Embedding模型 | 商品描述 | 素材列表 | ChromaDB |
| 2.4 Prompt构造 | 拼接生成提示词 | 无 | 商品信息+知识+模板 | 完整Prompt | - |
| 2.5 LLM生成剧本 | 生成带货文案 | LLM (GPT-4/Claude Sonnet) | Prompt | 剧本JSON | - |
| 2.6 剧本解析 | 解析LLM输出 | 无 | JSON字符串 | 结构化剧本 | - |
| 2.7 剧本入库 | 保存到数据库 | 无 | 剧本数据 | script_id | MySQL |

---

### 步骤 ③：视频生成阶段（异步任务链）

```
剧本数据 ──→ TTS配音 ──→ 图片准备 ──→ 视频合成 ──→ 成品上传
    │           │           │           │           │
 读取剧本    调用TTS     调用图像模型   视频合成引擎   MinIO
```

| 子步骤 | 动作 | 调用模型 | 输入 | 输出 | 存储位置 |
|---|---|---|---|---|---|
| 3.1 读取剧本 | 从MySQL获取剧本 | 无 | script_id | 剧本JSON | - |
| 3.2 TTS配音 | 生成配音音频 | TTS模型 (火山引擎/Edge TTS) | full_text | MP3文件 | MinIO |
| 3.3 场景图片生成 | 生成/获取配图 | 文生图模型 (火山引擎SD/DALL-E) | image_keyword | PNG文件 | MinIO |
| 3.4 字幕生成 | 生成字幕文件 | 无（从剧本提取） | 剧本body | SRT文件 | MinIO |
| 3.5 视频合成 | 合成最终视频 | 视频合成引擎 (FFmpeg/MoviePy) | 音频+图片+字幕 | MP4文件 | 本地临时 |
| 3.6 成品上传 | 上传到MinIO | 无 | MP4文件 | MinIO路径 | MinIO |
| 3.7 状态更新 | 更新项目状态 | 无 | 生成结果 | 状态变更 | MySQL |

---

### 步骤 ④：输出交付阶段

```
前端轮询 ──→ 获取状态 ──→ 展示预览 ──→ 导出下载
    │           │           │           │
 定时请求     查询MySQL    视频播放     MinIO下载
```

| 子步骤 | 动作 | 调用模型 | 输入 | 输出 |
|---|---|---|---|---|
| 4.1 状态查询 | 前端轮询项目状态 | 无 | project_id | 状态+进度 |
| 4.2 视频预览 | 在线播放视频 | 无 | video_url | 播放器 |
| 4.3 视频导出 | 下载视频文件 | 无 | video_url | MP4文件 |

---

## 3. 模型调用时机详解

### 3.1 同步调用（API请求内完成）

```
┌────────────────────────────────────────────────────────────┐
│                    同步调用链路                               │
│                                                            │
│  POST /api/v1/projects/{id}/generate                       │
│       │                                                    │
│       ├─→ 2.2 知识检索: Embedding模型 (50-100ms)            │
│       │       输入: 商品描述文本                              │
│       │       输出: 相关知识片段                              │
│       │                                                    │
│       ├─→ 2.5 LLM生成剧本: GPT-4/Claude (2-5s)             │
│       │       输入: 完整Prompt                              │
│       │       输出: 剧本JSON                                │
│       │                                                    │
│       └─→ 返回: script_id + "剧本已生成"                     │
└────────────────────────────────────────────────────────────┘
```

### 3.2 异步调用（Celery Worker执行）

```
┌────────────────────────────────────────────────────────────┐
│                    异步调用链路                               │
│                                                            │
│  Celery Task: generate_video_task                          │
│       │                                                    │
│       ├─→ 3.2 TTS配音: 火山引擎TTS (3-10s)                  │
│       │       输入: 配音文本                                 │
│       │       输出: MP3音频文件                              │
│       │                                                    │
│       ├─→ 3.3 图片生成: 文生图模型 (5-15s)                   │
│       │       输入: 场景描述关键词                            │
│       │       输出: PNG图片文件                              │
│       │                                                    │
│       ├─→ 3.5 视频合成: FFmpeg (10-30s)                     │
│       │       输入: 音频+图片+字幕                           │
│       │       输出: MP4视频文件                              │
│       │                                                    │
│       └─→ 完成: 更新状态为completed                         │
└────────────────────────────────────────────────────────────┘
```

---

## 4. 模型调用清单

### 4.1 文本生成模型 (LLM)

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 剧本生成 | GPT-4o | Claude Sonnet | 步骤2.5 同步 | 2-5s |
| 剧本优化/改写 | GPT-4o-mini | Claude Haiku | 剧本干预 同步 | 1-3s |
| 方法论提炼 | GPT-4o | Claude Sonnet | 灵感模板生成 异步 | 3-8s |
| 商品信息解析 | GPT-3.5-turbo | Claude Haiku | 步骤2.1 同步 | 0.5-1s |

### 4.2 多模态理解模型 (Vision)

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 素材图片理解 | GPT-4V | Claude Vision | 步骤1.2 异步 | 2-5s |
| 视频关键帧分析 | GPT-4V | Claude Vision | 视频切片 异步 | 5-10s |

### 4.3 Embedding模型

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 知识库检索 | text-embedding-3-small | bge-large-zh | 步骤2.2 同步 | 50-100ms |
| 素材向量化 | text-embedding-3-small | bge-large-zh | 步骤1.4 异步 | 50-100ms |
| 素材语义检索 | text-embedding-3-small | bge-large-zh | 检索接口 同步 | 50-100ms |

### 4.4 图像生成模型

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 场景配图生成 | 火山引擎SD | DALL-E 3 | 步骤3.3 异步 | 5-15s |
| 商品图生成 | 火山引擎SD | Midjourney API | 素材补充 异步 | 5-15s |

### 4.5 语音合成模型 (TTS)

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 配音生成 | 火山引擎TTS | Edge TTS | 步骤3.2 异步 | 3-10s |
| 多语种配音 | 火山引擎TTS | Azure TTS | 多语种场景 异步 | 3-10s |

### 4.6 视频生成模型（进阶）

| 调用场景 | 推荐模型 | 备选模型 | 调用时机 | 预估耗时 |
|---|---|---|---|---|
| 文生视频 | 火山引擎视频生成 | Runway Gen-3 | 进阶功能 异步 | 30-120s |
| 图生视频 | 火山引擎视频生成 | Stable Video | 进阶功能 异步 | 30-120s |

---

## 5. 数据对接格式

### 5.1 步骤间数据流转

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         数据流转格式定义                                      │
│                                                                             │
│  ① 素材准备 → ② 剧本生成                                                    │
│  ──────────────────────                                                     │
│  接口: MaterialService.search_materials(query, type, top_k)                 │
│  输入: 检索关键词 + 素材类型 + 返回数量                                        │
│  输出: List[{id, url, tags, ai_features}]                                   │
│                                                                             │
│  ② 剧本生成 → ③ 视频生成                                                    │
│  ──────────────────────                                                     │
│  接口: Script.content (JSON字段)                                            │
│  格式:                                                                      │
│  {                                                                          │
│    "opening": "开场白文本",                                                  │
│    "body": [                                                                │
│      {                                                                      │
│        "scene": 1,                                                          │
│        "text": "分镜台词",                                                   │
│        "duration_sec": 5,                                                   │
│        "image_keyword": "配图描述",                                          │
│        "tts_audio_url": null,    // TTS完成后回填                            │
│        "image_url": null         // 图片生成后回填                           │
│      }                                                                      │
│    ],                                                                       │
│    "closing": "结尾话术",                                                    │
│    "full_text": "完整配音文本"                                               │
│  }                                                                          │
│                                                                             │
│  ③ 视频生成 → ④ 输出交付                                                    │
│  ──────────────────────                                                     │
│  接口: Project.video_output_url                                             │
│  格式: MinIO路径字符串                                                       │
│  示例: "projects/1/output.mp4"                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 模型调用输入输出规范

#### LLM剧本生成

```python
# 输入: Prompt模板
prompt = f"""
你是一个专业的电商带货视频编剧。根据以下信息，生成一个{target_duration}秒的带货短视频剧本。

【商品信息】
标题: {product_info['title']}
卖点: {product_info['selling_points']}
价格: {product_info['price']}
目标人群: {product_info['target_audience']}

【参考知识】
{knowledge_context}

【参考素材】
{material_context}

【创作要求】
- 开场3秒内必须有Hook吸引注意力
- 每个分镜5-8秒，节奏紧凑
- 结尾引导下单

请严格按以下JSON格式输出：
{{
  "opening": "吸引人的开场白",
  "body": [
    {{"scene": 1, "text": "台词", "duration_sec": 5, "image_keyword": "配图描述"}}
  ],
  "closing": "引导下单结尾",
  "full_text": "完整配音文本"
}}
"""

# 输出: JSON字符串
response = llm_client.chat(prompt)
script_content = json.loads(response)
```

#### TTS配音生成

```python
# 输入
input = {
    "text": "完整配音文本",
    "voice_type": "zh-CN-XiaoxiaoNeural",  # 音色
    "speed": 1.0,                           # 语速
    "pitch": 0                              # 音调
}

# 输出
output = {
    "audio_path": "/tmp/tts_xxx.mp3",       # 本地音频路径
    "duration": 30,                          # 时长(秒)
    "sample_rate": 24000                     # 采样率
}
```

#### 文生图

```python
# 输入
input = {
    "prompt": "场景描述关键词",
    "negative_prompt": "模糊, 低质量",
    "width": 1080,
    "height": 1920,      # 竖版9:16
    "num_images": 1
}

# 输出
output = {
    "image_path": "/tmp/img_xxx.png",        # 本地图片路径
    "width": 1080,
    "height": 1920
}
```

---

## 6. 异步任务编排

### 6.1 Celery任务链路

```python
# 任务编排（使用Celery Canvas）
from celery import chain, group, chord

def submit_video_generation(project_id: int, script_id: int):
    """提交视频生成任务链"""

    # 方案A: 串行执行（当前实现）
    task_chain = chain(
        generate_tts_audio.s(project_id, script_id),      # Step 1: TTS
        generate_scene_images.s(project_id, script_id),    # Step 2: 配图
        compose_video.s(project_id, script_id),            # Step 3: 合成
        finalize_video.s(project_id, script_id),           # Step 4: 上传+状态更新
    )
    task_chain.apply_async()

    # 方案B: 并行优化（进阶）
    # TTS和配图可以并行执行
    parallel_tasks = group(
        generate_tts_audio.si(project_id, script_id),
        generate_scene_images.si(project_id, script_id),
    )
    task_chain = chain(
        parallel_tasks,                                    # TTS和配图并行
        compose_video.s(project_id, script_id),            # 合成（依赖两者完成）
        finalize_video.s(project_id, script_id),           # 最终处理
    )
    task_chain.apply_async()
```

### 6.2 任务状态追踪

```
┌────────────────────────────────────────────────────────────────┐
│                     任务状态机                                   │
│                                                                │
│  draft ──→ script_ready ──→ processing ──→ completed           │
│                │                  │              │              │
│                │                  ├──→ failed    │              │
│                │                  │      │       │              │
│                │                  │      ▼       │              │
│                │                  │   retrying ──┘              │
│                │                  │                             │
│                └──→ failed        └──→ cancelled                │
│                                                                │
│  processing 子状态（存储在 Celery Task Meta）:                   │
│    - tts_generating: TTS生成中                                  │
│    - image_generating: 配图生成中                                │
│    - video_composing: 视频合成中                                 │
│    - uploading: 上传中                                          │
└────────────────────────────────────────────────────────────────┘
```

### 6.3 进度反馈机制

```python
# Celery任务中更新进度
@celery_app.task(bind=True)
def generate_video_task(self, project_id: int, script_id: int):
    # 更新任务元数据（前端可通过WebSocket或轮询获取）
    self.update_state(state='PROGRESS', meta={
        'step': 'tts_generating',
        'progress': 10,
        'message': '正在生成配音...'
    })

    # TTS生成...

    self.update_state(state='PROGRESS', meta={
        'step': 'image_generating',
        'progress': 40,
        'message': '正在生成场景配图...'
    })

    # 配图生成...

    self.update_state(state='PROGRESS', meta={
        'step': 'video_composing',
        'progress': 70,
        'message': '正在合成视频...'
    })

    # 视频合成...

    self.update_state(state='PROGRESS', meta={
        'step': 'uploading',
        'progress': 90,
        'message': '正在上传成品...'
    })

    # 上传完成...
    return {'status': 'completed', 'video_url': '...'}
```

---

## 7. 错误处理与重试策略

### 7.1 模型调用重试

| 模型类型 | 重试次数 | 重试间隔 | 降级策略 |
|---|---|---|---|
| LLM | 3次 | 1s/2s/4s 指数退避 | 降级到更小模型 |
| TTS | 3次 | 1s/2s/4s | 使用Edge TTS免费API |
| 文生图 | 2次 | 2s/4s | 使用默认模板图 |
| Embedding | 3次 | 0.5s/1s/2s | 降级到关键词检索 |

### 7.2 任务级错误处理

```python
@celery_app.task(bind=True, max_retries=3)
def generate_video_task(self, project_id: int, script_id: int):
    try:
        # 执行任务链...
        pass
    except TTSServiceError as exc:
        # TTS失败：重试，超过次数标记失败
        logger.error(f"TTS失败: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    except ImageGenerationError as exc:
        # 配图失败：使用默认图片兜底
        logger.warning(f"配图失败，使用默认图片: {exc}")
        use_default_images = True

    except VideoComposeError as exc:
        # 视频合成失败：不可降级，标记失败
        logger.error(f"视频合成失败: {exc}")
        update_project_status(project_id, "failed", str(exc))
        raise

    except Exception as exc:
        # 未知错误
        logger.error(f"未知错误: {exc}", exc_info=True)
        update_project_status(project_id, "failed", "系统内部错误")
        raise
```

---

## 8. 数据流向图（完整版）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           完整数据流向图                                      │
│                                                                             │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐           │
│  │  前端     │     │  MySQL   │     │  MinIO   │     │ ChromaDB │           │
│  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘           │
│       │                │                │                │                  │
│       │ ①创建项目       │                │                │                  │
│       ├───────────────→│                │                │                  │
│       │                │                │                │                  │
│       │ ②上传素材       │                │                │                  │
│       ├────────────────┼───────────────→│                │                  │
│       │                │                │                │                  │
│       │                │ ③AI分析+向量化  │                │                  │
│       │                │────────────────┼───────────────→│                  │
│       │                │                │                │                  │
│       │ ④提交生成       │                │                │                  │
│       ├───────────────→│                │                │                  │
│       │                │                │                │                  │
│       │                │ ⑤RAG检索       │                │                  │
│       │                │────────────────┼───────────────→│                  │
│       │                │                │                │                  │
│       │                │ ⑥返回知识片段   │                │                  │
│       │                │←───────────────┼────────────────│                  │
│       │                │                │                │                  │
│       │                │ ⑦调用LLM生成剧本│                │                  │
│       │                │───────→[LLM API]               │                  │
│       │                │                │                │                  │
│       │                │ ⑧保存剧本      │                │                  │
│       │                │───────→[scripts表]              │                  │
│       │                │                │                │                  │
│       │ ⑨返回剧本       │                │                │                  │
│       │←───────────────│                │                │                  │
│       │                │                │                │                  │
│       │ ⑩提交视频任务   │                │                │                  │
│       ├───────────────→│                │                │                  │
│       │                │ ⑪发送Celery    │                │                  │
│       │                │───────→[Redis] │                │                  │
│       │                │                │                │                  │
│  ─────┼────────────────┼────────────────┼────────────────┼─────────         │
│       │                │                │                │   Celery Worker  │
│       │                │ ⑫TTS配音       │                │                  │
│       │                │───────→[TTS API]               │                  │
│       │                │ ⑬上传音频       │                │                  │
│       │                │───────────────→│                │                  │
│       │                │                │                │                  │
│       │                │ ⑭生成配图       │                │                  │
│       │                │───────→[SD API]│                │                  │
│       │                │ ⑮上传图片       │                │                  │
│       │                │───────────────→│                │                  │
│       │                │                │                │                  │
│       │                │ ⑯合成视频       │                │                  │
│       │                │───────→[FFmpeg]│                │                  │
│       │                │ ⑰上传成品       │                │                  │
│       │                │───────────────→│                │                  │
│       │                │                │                │                  │
│       │                │ ⑱更新状态       │                │                  │
│       │                │───────→[projects表]             │                  │
│  ─────┼────────────────┼────────────────┼────────────────┼─────────         │
│       │                │                │                │                  │
│       │ ⑲轮询状态       │                │                │                  │
│       ├───────────────→│                │                │                  │
│       │ ⑳返回状态+URL  │                │                │                  │
│       │←───────────────│                │                │                  │
│       │                │                │                │                  │
│       │ ㉑播放视频       │                │                │                  │
│       ├────────────────┼───────────────→│                │                  │
│       │                │                │                │                  │
└───────┴────────────────┴────────────────┴────────────────┴──────────────────┘
```

---

## 9. 性能优化建议

### 9.1 模型调用优化

| 优化点 | 策略 | 预期收益 |
|---|---|---|
| LLM调用 | 使用流式响应、缓存相似Prompt | 减少等待时间50% |
| TTS生成 | 分段生成、并行处理 | 减少耗时30% |
| 图片生成 | 预生成常用场景图、使用缓存 | 减少调用次数60% |
| Embedding | 批量向量化、本地缓存 | 减少API调用80% |

### 9.2 任务编排优化

```python
# 优化前：串行执行（总耗时 = TTS + 图片 + 合成）
total_time = 10s + 15s + 20s = 45s

# 优化后：TTS和图片并行（总耗时 = max(TTS, 图片) + 合成）
total_time = max(10s, 15s) + 20s = 35s

# 进一步优化：分段并行（每个分镜独立处理）
total_time = 25s  # 大幅减少
```

### 9.3 缓存策略

```
┌────────────────────────────────────────────────────────────┐
│                      缓存层级                               │
│                                                            │
│  L1: 内存缓存 (Redis)                                       │
│    - 热点商品信息 (TTL: 1h)                                  │
│    - 常用Prompt模板 (TTL: 24h)                              │
│    - 用户会话数据 (TTL: 30min)                              │
│                                                            │
│  L2: 文件缓存 (MinIO)                                       │
│    - 生成的素材 (永久)                                       │
│    - 中间产物 (TTL: 7d)                                     │
│                                                            │
│  L3: 向量缓存 (ChromaDB)                                    │
│    - Embedding向量 (永久)                                   │
│    - 检索结果 (TTL: 1h)                                     │
└────────────────────────────────────────────────────────────┘
```

---

## 10. 监控与可观测性

### 10.1 关键指标

| 指标 | 计算方式 | 告警阈值 |
|---|---|---|
| 任务成功率 | 成功数/总数 | < 95% |
| 平均生成时长 | 从提交到完成 | > 60s |
| LLM调用延迟 | API响应时间 | > 10s |
| TTS调用延迟 | API响应时间 | > 15s |
| 任务队列深度 | Redis队列长度 | > 100 |

### 10.2 链路追踪

```python
# 使用OpenTelemetry进行链路追踪
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("generate_script")
async def generate_script(project_id: int):
    span = trace.get_current_span()
    span.set_attribute("project_id", project_id)

    with tracer.start_as_current_span("llm_call"):
        # LLM调用
        pass

    with tracer.start_as_current_span("save_script"):
        # 保存剧本
        pass
```

---

## 11. 实现优先级

| 优先级 | 链路 | 依赖 | 预估工时 |
|---|---|---|---|
| P0 | ② 剧本生成（基础版） | LLM API | 2天 |
| P0 | ③ 视频生成（Mock版） | 无 | 1天 |
| P0 | ④ 状态查询+预览 | MySQL | 1天 |
| P1 | ① 素材上传+管理 | MinIO | 2天 |
| P1 | ③ TTS配音（真实） | TTS API | 1天 |
| P1 | ③ 配图生成（真实） | SD API | 1天 |
| P1 | ③ 视频合成（真实） | FFmpeg | 2天 |
| P2 | ① 素材AI分析 | Vision API | 2天 |
| P2 | ② RAG知识检索 | ChromaDB | 1天 |
| P2 | ③ 视频生成模型 | 视频API | 3天 |
