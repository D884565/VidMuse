# VidMuse 后端视频生成数据流转文档

## 一、视频生成完整流程

整个视频生成分为两大阶段：**剧本生成（同步）** 和 **视频生产（Celery 异步任务）**。

### 阶段 1：项目创建 + 剧本生成（同步）

入口：`POST /generate/v1/projects`

1. 用户提交 `ProjectCreate`，包含 `title`、`user_prompt`、`style`、`target_audience`、`key_points`、`avoid`、`rag_weight`、`target_duration`、`voice_type`、`reference_images`、`product_url` 等字段
2. 如果提供了 `product_url`，通过 `product_crawl_service.crawl()` 抓取商品信息，转为 JSON 存入 `project.product_info`
3. 写入 `projects` 表，状态为 `draft`
4. 调用 `script_generation_service.generate_script()` 生成剧本（LLM 调用），将每个场景写入 `frames` 表，项目状态变为 `script_ready`
5. 调用 `video_generation_service.submit_generation_task()` 提交 Celery 异步任务，项目状态变为 `processing`

### 阶段 2：视频生产（Celery 异步任务）

文件：`backend/v1/app/generate/temp/video_tasks.py`

| 步骤 | 操作 | 输入 | 输出 |
|------|------|------|------|
| Step 1 | 读取帧数据 | - | frames 列表 |
| Step 2 | 项目级 TTS | frame.ai_params.text（拼接） | project.audio_url |
| Step 2.5 | 帧级 TTS | frame.ai_params.text | frame.audio_url |
| Step 3 | 图片生成 | frame.description | frame.image_url |
| Step 4 | 视频生成 | frame.prompt + frame.image_url | 帧视频片段 |
| Step 5 | 拼接 | 所有帧视频片段 | 合并视频 |
| Step 5.5 | 音频合并 | TTS 配音 + 合并视频 | 带配音视频 |
| Step 6 | 上传 | 成品视频 | project.video_output_url |

---

## 二、LLM 调用详情

### 调用 1：剧本生成

**文件**：`backend/v1/app/generate/service/script_generation.py` (第 348-390 行)

**System Prompt**：
```
你是一个专业的带货视频编剧，擅长创作短视频剧本。
你的输出必须是严格的 JSON 格式，不要包含任何其他文字。
image_prompt 要详细描述画面（主体、背景、光线、色调），用于 AI 图片生成。
video_prompt 要描述镜头运动和动态效果，用于 AI 视频生成。
overlay 用于指定画面上叠加的关键文字，简短有力，不超过10个字，用于提高转化率。
```

**User Prompt 结构**（由 `_build_prompt()` 方法组装）：

```
你是一个专业的带货视频编剧...请生成一个约{target_duration}秒的带货短视频剧本。

## 用户创作意图（必须严格遵循）
{project.user_prompt}

## 补充要求
- 风格：{style}
- 目标受众：{target_audience}
- 关键卖点：{key_points}
- 避免内容：{avoid}

## 商品信息
- 标题：{title}
- 描述：{description}
- 价格：{price}
- 规格：{specs}

## 用户提供的参考图片
{reference_images URLs}

## 参考资料（仅供参考借鉴，不要照搬）
### 参考剧本模板
{RAG 检索结果}
### 参考视觉素材
{RAG 检索结果}
### 商品知识参考
{RAG 检索结果}

## 输出要求
{JSON 模板}

## 场景类型说明
{场景类型定义}

## 注意事项
{生成注意事项}
```

**调用参数**：
- `temperature`: 0.7
- `max_tokens`: 4096

---

### 调用 2：对话式调整 - 影响范围分析

**文件**：`backend/v1/app/generate/service/chat_service.py` (第 192-232 行)

**System Prompt**：
```
你是视频调整助手，判断用户想调整哪些场景。只返回JSON。
```

**User Prompt**：
```
用户想要调整视频。以下是当前视频的场景列表：
  场景1 (id=xxx, type=0): 画面描述前80字...
  场景2 ...

用户的调整要求：{user_message}

请判断影响范围，返回 JSON：{"scope": "all" | "single", "frame_id": null | int}
```

**调用参数**：
- `temperature`: 0.3
- `max_tokens`: 256

---

### 调用 3：对话式调整 - 帧内容重新生成

**文件**：`backend/v1/app/generate/service/chat_service.py` (第 278-297 行)

**System Prompt**：
```
你是带货视频编剧。只返回JSON。
```

**User Prompt**（由 `_build_frame_regenerate_prompt()` 组装）：
```
你是一个专业的带货视频编剧。请为以下场景重新生成内容。

## 商品信息
- 标题：{project.title}
- 描述：{project.description}

## 用户原始意图
{project.user_prompt}

## 当前场景
- 类型：{frame.scene_type}
- 序号：{frame.sequence}
- 当前画面描述：{frame.description}

## 对话历史
user: xxx
assistant: xxx
（最近10条）

## 调整指令
{instruction}

请返回 JSON：
{"image_prompt": "...", "video_prompt": "...", "text": "...", "overlay_text": "...", "camera": "...", "mood": "..."}
```

**调用参数**：
- `temperature`: 0.7
- `max_tokens`: 1024

---

## 三、模型输出格式

### 剧本生成输出格式

```json
{
  "video_meta": {
    "product_name": "商品名称",
    "target_duration": 15,
    "style": "fashion/tech/food/lifestyle",
    "aspect_ratio": "9:16",
    "hook_line": "一句话开场金句"
  },
  "scenes": [
    {
      "scene_id": 1,
      "type": "hook/selling_point/detail/social_proof/price/cta",
      "duration": 5,
      "text": "配音文案（口语化）",
      "voice_style": "excited/confident/urgent/warm/professional",
      "visual": {
        "image_prompt": "详细画面描述（主体、背景、光线、色调、构图）",
        "video_prompt": "镜头运动和动态效果描述",
        "camera": "push_in/pull_out/pan_left/pan_right/static/close_up/wide_shot",
        "mood": "warm/bright/dark/energetic/elegant",
        "overlay": {
          "text": "叠加文字（不超过10字）",
          "position": "top/center/bottom",
          "style": "highlight/price_tag/call_to_action/subtle"
        }
      }
    }
  ],
  "audio": {
    "tts_voice": "zh_female_cancan_mars_bigtts",
    "bgm": "背景音乐风格描述",
    "bgm_volume": 0.3
  }
}
```

### 对话调整输出格式

**影响范围分析**：
```json
{
  "scope": "all" | "single",
  "frame_id": null | int
}
```

**帧重新生成**：
```json
{
  "image_prompt": "...",
  "video_prompt": "...",
  "text": "...",
  "overlay_text": "...",
  "camera": "...",
  "mood": "..."
}
```

---

## 四、数据流转图

```
用户输入 (ProjectCreate)
    │
    ▼
[Project 表] ── title, description, user_prompt, style, target_audience,
                key_points, avoid, rag_weight, target_duration, voice_type,
                product_url, product_info(JSON), reference_images(JSON)
    │
    │  script_generation_service.generate_script()
    │  ├── RAG 检索 → 参考文本
    │  ├── _build_prompt() → 完整 prompt
    │  ├── LLM 调用 → JSON 剧本
    │  └── 逐场景写入 Frame 表
    │
    ▼
[Frame 表] ── sequence, scene_type(int), description(=image_prompt),
              prompt(=video_prompt), text_overlay, duration, ai_params(JSON),
              metadata_(JSON), status=0(待生成)
    │
    │  video_generation_service.submit_generation_task()
    │  → Celery 异步任务 generate_video_task
    │
    ▼
[Step 2: TTS]
    │  读取 frame.ai_params.text → 拼接 → 火山引擎 TTS API
    │  → project.audio_url (项目级)
    │  → frame.audio_url (帧级)
    │
    ▼
[Step 3: 图片生成]
    │  读取 frame.description → 火山引擎 Seedream 4.5 API
    │  参考图: product_info.main_images[0]
    │  → frame.image_url, frame.status=2
    │
    ▼
[Step 4: 视频生成]
    │  读取 frame.prompt + frame.ai_params(camera,mood)
    │  + frame.image_url 作为首帧
    │  → Seedance 1.5 API (固定5秒)
    │  → 裁剪/补时到 frame.duration
    │
    ▼
[Step 5: 拼接]
    │  FFmpeg concat 所有帧视频片段
    │
    ▼
[Step 5.5: 音频合并]
    │  FFmpeg replace_audio: TTS配音 → 视频音轨
    │
    ▼
[Step 6: 上传]
    │  → project.video_output_url
    │  → Asset 表记录
    │  → project.status = "completed"
```

---

## 五、关键数据映射关系

| LLM 输出字段 | 数据库字段 | 用途 |
|-------------|-----------|------|
| `scene.type` (字符串) | `frame.scene_type` (整数) | 场景类型，通过 SCENE_TYPE_MAP 转换 |
| `visual.image_prompt` | `frame.description` | 用于图片生成 prompt |
| `visual.video_prompt` | `frame.prompt` | 用于视频生成 prompt |
| `visual.overlay.text` | `frame.text_overlay` | 画面叠加文字 |
| `text` | `frame.ai_params.text` | 配音文案 |
| `voice_style` | `frame.ai_params.voice_style` | 语音风格 |
| `camera` | `frame.ai_params.camera` | 镜头运动 |
| `mood` | `frame.ai_params.mood` | 画面氛围 |

### 场景类型映射 (SCENE_TYPE_MAP)

| LLM 输出 | 数据库值 | 含义 |
|----------|---------|------|
| hook | 0 | 开场吸引 |
| selling_point | 1 | 卖点展示 |
| price | 1 | 价格展示 |
| detail | 2 | 细节展示 |
| social_proof | 2 | 社会证明 |
| cta | 4 | 行动号召 |

---

## 六、核心文件索引

| 文件 | 职责 |
|------|------|
| `backend/v1/app/generate/controller/generation.py` | API 路由层 |
| `backend/v1/app/generate/service/script_generation.py` | 剧本生成服务 |
| `backend/v1/app/generate/service/video_generation.py` | 视频生成调度服务 |
| `backend/v1/app/generate/temp/video_tasks.py` | Celery 异步任务 |
| `backend/v1/app/generate/service/image_generation_service.py` | 图片生成服务 |
| `backend/v1/app/generate/service/video_composer.py` | 视频合成服务 |
| `backend/v1/app/generate/service/tts_service.py` | TTS 语音合成服务 |
| `backend/v1/app/generate/service/chat_service.py` | 对话式调整服务 |
| `backend/providers/volcano.py` | 火山引擎统一客户端 |
| `backend/providers/dto/schema.py` | 请求/响应数据结构 |
