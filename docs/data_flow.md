# VidMuse 视频生成 - 完整数据流转链路

## 总览

```
商品信息（Project 表）
    ↓
Step 1: LLM 生成分镜脚本（火山引擎 doubao-seed-2.0-pro）
    ↓
分镜脚本 JSON（存入 scripts 表）
    ↓
Step 2: TTS 生成配音（火山引擎 TTS API）
    ↓
audio.mp3
    ↓
Step 3: 为每个场景生成图片（火山引擎 Seedream 5.0）
    ↓
image_urls[]
    ↓
Step 4: 为每个场景生成视频（火山引擎 Seedance 1.5，图片作首帧）
    ↓
video_clips[]
    ↓
Step 5: FFmpeg 拼接所有视频片段
    ↓
final_video.mp4
    ↓
Step 6: 上传 TOS，更新项目状态
```

---

## 技术栈

| 环节 | 服务 | 模型/API |
|------|------|----------|
| LLM 剧本生成 | 火山引擎 Ark | doubao-seed-2.0-pro |
| TTS 语音合成 | 火山引擎 TTS | openspeech.bytedance.com |
| 图片生成 | 火山引擎 Ark | doubao-seedream-5-0-260128 |
| 视频生成 | 火山引擎 Ark | Seedance 1.5 |
| 视频拼接 | 本地 FFmpeg | - |
| 对象存储 | 火山引擎 TOS | tos-cn-beijing.volces.com |

---

## Step 1: LLM 生成分镜脚本

### 入口

**文件**: `backend/v1/app/generate/service/script_generation.py`
**类**: `ScriptGenerationService`
**方法**: `generate_script(db, project_id, target_duration)`

### 输入

从 MySQL 读取 Project 表：

```python
project = db.execute(select(Project).where(Project.id == project_id))
# project.title       - 商品标题
# project.description - 商品描述
# project.product_info - 商品详情
```

### 操作

1. **检索参考资料**（当前为 Mock，TODO: 接入 ChromaDB）

2. **构造 Prompt**
   ```
   你是一个专业的带货视频编剧...
   商品标题：{project.title}
   商品描述：{project.description}
   商品详情：{project.product_info}
   ```

3. **调用 LLM**
   ```python
   from backend.providers import VolcanoLLM, ChatRequest, ChatMessage

   self.llm = VolcanoLLM(key=None, model_name=None)  # 单例
   request = ChatRequest(
       messages=[
           ChatMessage(role="system", content="你是一个专业的带货视频编剧..."),
           ChatMessage(role="user", content=prompt),
       ],
       temperature=0.7,
       max_tokens=4096,
   )
   response = await loop.run_in_executor(None, self.llm.chat, request)
   ```

4. **VolcanoLLM 内部调用**（`backend/providers/volcano.py`）
   ```python
   self.client = Ark(
       api_key=os.getenv("DOUBAO_SEED_API_KEY"),
       base_url="https://ark.cn-beijing.volces.com/api/v3",
   )
   result = self.client.chat.completions.create(
       messages=[...],
       model="doubao-seed-2.0-pro",
       stream=False,
   )
   ```

### 输出

分镜脚本 JSON，存入 `scripts` 表：

```json
{
  "video_meta": {
    "product_name": "粉色碎花裙",
    "target_duration": 15,
    "style": "fashion",
    "aspect_ratio": "9:16",
    "hook_line": "还在为选裙子发愁？"
  },
  "scenes": [
    {
      "scene_id": 1,
      "type": "hook",
      "duration": 5,
      "text": "姐妹们！这条裙子我穿了一周都没换！",
      "voice_style": "excited",
      "visual": {
        "image_prompt": "一位年轻女性穿着粉色碎花连衣裙，正面展示，时尚街拍，自然光线，甜美笑容，背景模糊",
        "video_prompt": "镜头从全身缓慢推近至腰部特写，展示收腰设计",
        "camera": "push_in",
        "mood": "warm",
        "overlay": {
          "text": "粉色碎花裙",
          "position": "bottom",
          "style": "highlight"
        }
      }
    },
    {
      "scene_id": 2,
      "type": "selling_point",
      "duration": 5,
      "text": "看这个收腰设计，吃撑了也不勒肚子！",
      "voice_style": "confident",
      "visual": {
        "image_prompt": "连衣裙腰部细节特写，收腰设计，褶皱处理，模特侧面展示",
        "video_prompt": "镜头从左向右缓慢平移，展示腰部线条",
        "camera": "pan_left",
        "mood": "warm",
        "overlay": {
          "text": "法式收腰",
          "position": "bottom",
          "style": "highlight"
        }
      }
    }
  ],
  "audio": {
    "tts_voice": "zh_female_cancan_mars_bigtts",
    "bgm": "轻松愉快的背景音乐",
    "bgm_volume": 0.3
  }
}
```

### 数据流转

```
Project 表 → ScriptGenerationService → Script 表
```

---

## Step 2: TTS 生成配音

### 入口

**文件**: `backend/v1/app/generate/service/tts_service.py`
**类**: `TtsService`
**方法**: `generate_audio(text, voice_type)`

### 输入

```python
# 拼接所有场景的文案
full_text = " ".join([scene.get("text", "") for scene in scenes])
tts_voice = audio_config.get("tts_voice", "zh_female_cancan_mars_bigtts")
```

### 操作

调用火山引擎 TTS HTTP API：

```python
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer;{self.token}",  # TTS_SECRET_KEY
}

payload = {
    "app": {
        "appid": self.app_id,  # TTS_ACCESS_KEY
        "token": "fake_token",
        "cluster": "volcano_tts",
    },
    "user": {
        "uid": "vidmuse_user",
    },
    "audio": {
        "voice_type": voice_type,  # "zh_female_cancan_mars_bigtts"
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
    },
    "request": {
        "reqid": uuid.uuid4().hex,
        "text": text,
        "operation": "query",
    },
}

response = requests.post(TTS_API_URL, json=payload, headers=headers, timeout=30)
```

### 输出

- 本地音频文件：`/tmp/tts_{uuid}.mp3`
- 上传到 TOS：`projects/{project_id}/audio_{script_id}.mp3`
- 记录到 Asset 表（type=3，音频）

### 数据流转

```
Script.content → TtsService → /tmp/tts_xxx.mp3 → TOS → Asset 表
```

---

## Step 3: 为每个场景生成图片

### 入口

**文件**: `backend/v1/app/generate/service/image_generation_service.py`
**类**: `ImageGenerationService`
**方法**: `generate_scene_images(scenes, project_id, product_images)`

### 输入

```python
scenes = script_content.get("scenes", [])
# 每个 scene 包含 visual.image_prompt
```

### 操作

调用火山引擎 Ark 图片生成 API：

```python
IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
IMAGE_MODEL = "doubao-seedream-5-0-260128"

# 文生图
payload = {
    "model": IMAGE_MODEL,
    "prompt": image_prompt,
    "size": "2K",
    "response_format": "url",
    "sequential_image_generation": "disabled",
    "stream": False,
    "watermark": False,
}

# 图生图（有参考图时）
payload = {
    "model": IMAGE_MODEL,
    "prompt": image_prompt,
    "image": reference_image_url,  # 商品图片作为参考
    "size": "2K",
    "response_format": "url",
    "sequential_image_generation": "disabled",
    "stream": False,
    "watermark": False,
}

response = requests.post(
    IMAGE_API_URL,
    json=payload,
    headers={"Authorization": f"Bearer {self.api_key}"},
    timeout=60,
)
```

### 输出

- 图片 URL 列表：`["https://xxx/scene_1.png", "https://xxx/scene_2.png", ...]`
- 下载到本地 → 上传 TOS → 返回 HTTP URL

### 数据流转

```
scenes[].visual.image_prompt → ImageGenerationService → TOS URL → image_urls[]
```

---

## Step 4: 为每个场景生成视频

### 入口

**文件**: `backend/v1/app/generate/service/video_composer.py`
**类**: `VideoComposer`
**方法**: `compose(audio_path, scenes, image_urls, output_dir)`

### 输入

```python
scenes = script_content.get("scenes", [])
image_urls = ["https://xxx/scene_1.png", "https://xxx/scene_2.png", ...]
```

### 操作

为每个场景调用火山引擎 Seedance 1.5：

```python
# 构造 prompt
prompt = scene.visual.video_prompt + "\n镜头运动：" + camera + "\n氛围：" + mood

# 构造请求
video_request = VideoRequest(
    duration=duration,      # 2-10秒
    ratio="9:16",           # 竖屏
    generate_audio=False,   # 不生成音频，用 TTS
    draft=False,
    watermark=False,
)

# 调用视频生成（同步）
response = self.llm.generate_video_sync(
    request=video_request,
    prompt=prompt,
    image=image_url,  # 首帧图片
)
```

**VolcanoLLM.generate_video_sync 内部**：

```python
# 构造请求内容
content = [
    {"type": "text", "text": prompt},
    {"type": "image_url", "image_url": {"url": image_url}},  # 首帧
]

# 创建任务
create_result = self.client.content_generation.tasks.create(
    content=content,
    model=self.video_model,  # Seedance 1.5
    generate_audio=False,
    duration=duration,
    ratio="9:16",
)

# 轮询任务状态（最多 30 次，每次 10 秒）
while retry_count < max_retry:
    get_result = self.client.content_generation.tasks.get(task_id=task_id)
    if status == "succeeded":
        video_url = get_result.content.video_url
        break
    elif status == "failed":
        raise Exception(...)
    else:
        time.sleep(10)
```

### 输出

- 每个场景视频：`/tmp/project_xxx/scene_{i}_{uuid}.mp4`
- 视频 URL 列表

### 数据流转

```
scenes[].visual.video_prompt + image_urls[] → VideoComposer → video_paths[]
```

---

## Step 5: FFmpeg 拼接视频片段

### 入口

**文件**: `backend/v1/app/generate/service/video_composer.py`
**方法**: `_concat_videos(video_paths, output_dir)`

### 输入

```python
video_paths = [
    "/tmp/project_xxx/scene_0_xxx.mp4",
    "/tmp/project_xxx/scene_1_xxx.mp4",
    "/tmp/project_xxx/scene_2_xxx.mp4",
]
```

### 操作

```python
# 创建 concat 文件列表
with open(concat_file, "w") as f:
    for video_path in video_paths:
        f.write(f"file '{video_path}'\n")

# FFmpeg 拼接
cmd = [
    "ffmpeg",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_file,
    "-c", "copy",
    "-y",
    output_path,
]
subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

如果 FFmpeg 失败，使用 moviepy 作为 fallback：

```python
from moviepy import VideoFileClip, concatenate_videoclips

clips = [VideoFileClip(path) for path in video_paths]
final_clip = concatenate_videoclips(clips, method="compose")
final_clip.write_videofile(output_path, fps=24)
```

### 输出

- 拼接后的视频：`/tmp/project_xxx/concat_{uuid}.mp4`

### 数据流转

```
video_paths[] → FFmpeg concat → concat_video.mp4
```

---

## Step 6: 上传 TOS，更新项目状态

### 入口

**文件**: `backend/v1/app/generate/temp/video_tasks.py`
**函数**: `generate_video_task(project_id, script_id)`

### 操作

```python
# 上传成品视频到 TOS
video_object = f"projects/{project_id}/output.mp4"
get_storage_client().upload_file(video_path, video_object)

# 记录资产
db.add(Asset(
    user_id=project.user_id,
    type=2,  # 视频
    title="成品视频",
    url=video_object,
    format="mp4",
    source_type=1,  # AI生成
))

# 更新项目状态
project.video_output_url = video_object
project.status = "completed"
db.commit()
```

### 输出

- TOS 视频 URL：`projects/{project_id}/output.mp4`
- Project 表更新：`video_output_url`、`status = "completed"`
- Asset 表新增：视频资产记录

### 数据流转

```
concat_video.mp4 → TOS → Project.video_output_url
                      → Asset 表
```

---

## 完整调用链路图

```
API 请求
    ↓
VideoGenerationService.submit_generation_task()
    ↓
Celery 异步任务：generate_video_task()
    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: 读取 Script                                                     │
│     Script.content → script_content (dict)                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 2: TTS                                                             │
│     full_text → TtsService.generate_audio() → audio.mp3                 │
│     audio.mp3 → TOS → Asset(type=3)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 3: 图片生成                                                         │
│     scenes[].image_prompt → ImageGenerationService.generate_scene_images│
│     → image_urls[] (TOS URL)                                            │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 4: 视频生成                                                         │
│     scenes[].video_prompt + image_urls[] → VideoComposer.compose()      │
│     → video_paths[] (本地文件)                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 5: 视频拼接                                                         │
│     video_paths[] → FFmpeg concat → concat_video.mp4                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Step 6: 上传 & 更新                                                      │
│     concat_video.mp4 → TOS → Project.video_output_url                  │
│                           → Asset(type=2)                               │
│     Project.status = "completed"                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 数据格式汇总

| 步骤 | 输入 | 输出 | 存储位置 |
|------|------|------|----------|
| 1. LLM 剧本 | Project 表 | 分镜脚本 JSON | Script 表 |
| 2. TTS 配音 | scenes[].text | audio.mp3 | TOS + Asset 表 |
| 3. 图片生成 | scenes[].image_prompt | image_urls[] | TOS |
| 4. 视频生成 | scenes[].video_prompt + image_urls | video_paths[] | 本地临时目录 |
| 5. 视频拼接 | video_paths[] | concat_video.mp4 | 本地临时目录 |
| 6. 上传更新 | concat_video.mp4 | video_url | TOS + Project 表 |

---

## 关键配置（.env）

```bash
# 火山引擎 LLM
DOUBAO_SEED_API_KEY=xxx
DOUBAO_SEED=doubao-1.5-pro

# 火山引擎视频生成
DOUBAO_SEEDDANCE=seedance-1.5

# 火山引擎 TTS
TTS_ACCESS_KEY=xxx      # 作为 appid
TTS_SECRET_KEY=xxx      # 作为 access_token

# 火山引擎图片生成
IMAGE_API_KEY=xxx

# 火山引擎对象存储
TOS_ACCESS_KEY=xxx
TOS_SECRET_KEY=xxx
TOS_BUCKET_NAME=vidmuse
```

---

## 目录结构

```
backend/v1/app/generate/
├── controller/
│   └── generation.py              # API 控制器
├── dao/
│   ├── generation.py              # 数据访问
│   ├── project.py
│   └── script.py
├── service/
│   ├── script_generation.py       # Step 1: LLM 生成剧本
│   ├── tts_service.py             # Step 2: TTS 语音合成
│   ├── image_generation_service.py # Step 3: 图片生成
│   ├── image_service.py           # 图片处理（混合方案）
│   ├── video_composer.py          # Step 4+5: 视频生成+拼接
│   └── video_generation.py        # 视频生成调度
└── temp/
    ├── celery_app.py              # Celery 配置
    └── video_tasks.py             # Step 6: 异步任务主流程

backend/providers/
├── volcano.py                     # 火山引擎 API 封装
└── dto/
    └── schema.py                  # 数据模型定义
```

---

## 性能预估

| 步骤 | 耗时 | 说明 |
|------|------|------|
| LLM 剧本生成 | 3-5 秒 | doubao-seed-2.0-pro |
| TTS 配音 | 5-10 秒 | 全文一次性生成 |
| 图片生成 | 10-20 秒/张 | Seedream 5.0，可并行 |
| 视频生成 | 30-60 秒/段 | Seedance 1.5，轮询等待 |
| 视频拼接 | 2-5 秒 | FFmpeg 本地计算 |
| **总计（4场景）** | **约 3-5 分钟** | 主要耗时在视频生成 |
