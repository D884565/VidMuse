# 视频生成模块开发规格说明书

## 1. 概述

视频生成模块是 AIGC 带货视频生成系统的**执行引擎**，负责根据剧本和素材合成最终的带货视频。模块包括 TTS 配音、场景配图、视频合成、字幕生成等核心能力，支持一键成片、智能剪辑、分镜级干预等功能。

### 1.1 所属链路位置

```
剧本 + 素材 ──→ [视频生成] ──→ 成品视频
   (输入)        本模块范围      (输出)
```

### 1.2 核心能力

- **一键成片**：输入商品信息，端到端产出完整带货视频
- **智能剪辑**：基于剧本分镜自动完成画面拼接、转场、字幕、配音、配乐合成
- **分镜级干预**：支持对单个分镜重生成、替换素材、调整时长、修改台词
- **多格式导出**：支持竖版9:16、横版16:9等多种画幅

### 1.3 涉及的外部依赖

| 依赖 | 用途 |
|---|---|
| 火山引擎 TTS API | 语音合成 |
| 火山引擎 文生图 API | 场景配图生成 |
| FFmpeg / MoviePy | 视频合成 |
| MinIO | 素材和成品存储 |
| MySQL | 存储素材记录和项目状态 |
| Redis + Celery | 异步任务队列 |

---

## 2. 功能分级

### P0 必做

- TTS配音生成
- 场景配图（使用商品图或默认图）
- 基础视频合成（图片+音频+字幕）
- 任务进度查询
- 成品预览与导出

### P1 进阶

- 智能配图（AI生成场景图）
- 多语种TTS配音
- 转场效果
- BGM自动匹配
- 分镜级编辑
- 失败重试机制

### P2 加分项

- 视频生成模型（文生视频/图生视频）
- 高级转场动画
- 视频风格迁移
- A/B版本对比
- 画中画效果

---

## 3. 数据库表结构

### 3.1 materials 表（已有）

```sql
-- 素材表已在素材模块定义，此处补充视频生成相关的素材类型
-- type: 1=商品图 2=背景音乐 3=配音音频 4=字幕 5=成品视频 6=视频片段 7=场景配图
```

### 3.2 video_tasks 表（新增）

```sql
CREATE TABLE video_tasks (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT NOT NULL COMMENT '所属项目',
    script_id        BIGINT NOT NULL COMMENT '关联剧本',
    celery_task_id   VARCHAR(100) COMMENT 'Celery任务ID',
    status           VARCHAR(20) DEFAULT 'pending' COMMENT '状态：pending/processing/completed/failed',
    current_step     VARCHAR(50) COMMENT '当前步骤：tts/image/compose/upload',
    progress         INT DEFAULT 0 COMMENT '进度百分比(0-100)',
    error_message    TEXT COMMENT '失败原因',
    result_video_url VARCHAR(500) COMMENT '成品视频MinIO路径',
    started_at       TIMESTAMP NULL COMMENT '开始时间',
    completed_at     TIMESTAMP NULL COMMENT '完成时间',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    INDEX idx_project (project_id),
    INDEX idx_status (status),
    INDEX idx_celery_task (celery_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频生成任务表';
```

### 3.3 video_compositions 表（新增，用于分镜级干预）

```sql
CREATE TABLE video_compositions (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT NOT NULL COMMENT '所属项目',
    task_id          BIGINT COMMENT '关联的视频任务',
    scene_index      INT NOT NULL COMMENT '场景序号',
    audio_url        VARCHAR(500) COMMENT '该分镜的配音URL',
    image_url        VARCHAR(500) COMMENT '该分镜的配图URL',
    subtitle_text    TEXT COMMENT '该分镜的字幕文本',
    duration_sec     INT COMMENT '该分镜时长(秒)',
    transition_type  VARCHAR(20) DEFAULT 'fade' COMMENT '转场类型',
    status           VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    INDEX idx_project_scene (project_id, scene_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频分镜合成表';
```

---

## 4. API 接口定义

### 4.1 提交视频生成任务

```
POST /api/v1/projects/{project_id}/video/generate
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| script_id | int | 否 | 指定剧本ID（默认使用最新剧本） |
| voice_type | str | 否 | TTS音色 |
| output_format | str | 否 | 输出格式：9:16（竖版）/ 16:9（横版）/ 1:1 |
| bgm_style | str | 否 | BGM风格：upbeat/soft/energetic/none |

**响应：**

```json
{
    "code": "0000000",
    "message": "视频生成任务已提交",
    "data": {
        "task_id": 1,
        "project_id": 1,
        "script_id": 1,
        "status": "pending",
        "celery_task_id": "abc123-def456"
    }
}
```

### 4.2 查询任务进度

```
GET /api/v1/video-tasks/{task_id}/progress
```

**响应：**

```json
{
    "code": "0000000",
    "message": "操作成功",
    "data": {
        "task_id": 1,
        "status": "processing",
        "current_step": "compose",
        "progress": 65,
        "steps": [
            { "name": "tts", "status": "completed", "progress": 100 },
            { "name": "image", "status": "completed", "progress": 100 },
            { "name": "compose", "status": "processing", "progress": 30 },
            { "name": "upload", "status": "pending", "progress": 0 }
        ],
        "estimated_remaining_sec": 25
    }
}
```

### 4.3 获取项目视频任务列表

```
GET /api/v1/projects/{project_id}/video-tasks
```

### 4.4 预览视频

```
GET /api/v1/video-tasks/{task_id}/preview
```

**响应：**

```json
{
    "code": "0000000",
    "message": "操作成功",
    "data": {
        "video_url": "http://minio:9000/aigc-videos/projects/1/output.mp4",
        "duration": 30,
        "resolution": "1080x1920",
        "format": "mp4"
    }
}
```

### 4.5 导出视频

```
POST /api/v1/video-tasks/{task_id}/export
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| format | str | 否 | 导出格式：mp4/webm |
| quality | str | 否 | 质量：high/medium/low |
| resolution | str | 否 | 分辨率：1080x1920/720x1280/1280x720 |

### 4.6 分镜级干预

```
POST /api/v1/video-tasks/{task_id}/scenes/{scene_index}/intervene
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| action | str | 是 | 操作：regenerate/replace_audio/replace_image/change_duration/edit_subtitle |
| audio_url | str | 否 | 新配音URL（replace_audio时必填） |
| image_url | str | 否 | 新配图URL（replace_image时必填） |
| duration_sec | int | 新时长（change_duration时必填） |
| subtitle_text | str | 否 | 新字幕文本（edit_subtitle时必填） |

**响应：**

```json
{
    "code": "0000000",
    "message": "分镜更新成功，正在重新合成",
    "data": {
        "task_id": 2,
        "scene_index": 2,
        "status": "processing",
        "estimated_remaining_sec": 15
    }
}
```

### 4.7 一键成片

```
POST /api/v1/quick-generate
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| product_url | str | 否 | 商品链接（自动抓取信息） |
| product_image | file | 否 | 商品主图（上传） |
| product_title | str | 是 | 商品标题 |
| product_info | str | 否 | 商品详细信息 |
| target_duration | int | 否 | 目标时长，默认30 |
| auto_publish | bool | 否 | 生成后自动发布 |

**响应：**

```json
{
    "code": "0000000",
    "message": "一键成片任务已提交",
    "data": {
        "project_id": 1,
        "task_id": 1,
        "status": "processing"
    }
}
```

---

## 5. Service 层接口定义

### 5.1 VideoGenerationService

```python
class VideoGenerationService:
    """视频生成调度服务"""

    async def submit_generation_task(
        self,
        db: AsyncSession,
        project_id: int,
        script_id: int,
        voice_type: str = "zh-CN-XiaoxiaoNeural",
        output_format: str = "9:16",
        bgm_style: str = "none",
    ) -> VideoTask:
        """
        提交视频生成任务。

        流程：
        1. 校验项目和剧本状态
        2. 创建video_task记录
        3. 发送Celery异步任务
        4. 返回task_id
        """
        ...

    async def get_task_progress(
        self,
        db: AsyncSession,
        task_id: int,
    ) -> TaskProgress:
        """查询任务进度（从Celery Task Meta获取）"""
        ...

    async def get_project_tasks(
        self,
        db: AsyncSession,
        project_id: int,
    ) -> list[VideoTask]:
        """获取项目的所有视频任务"""
        ...

    async def intervene_scene(
        self,
        db: AsyncSession,
        task_id: int,
        scene_index: int,
        action: str,
        params: dict,
    ) -> VideoTask:
        """
        分镜级干预。

        流程：
        1. 校验任务状态
        2. 更新分镜数据
        3. 重新触发合成任务
        """
        ...
```

### 5.2 TTSService

```python
class TTSService:
    """TTS语音合成服务"""

    def generate_audio(
        self,
        text: str,
        voice_type: str = "zh-CN-XiaoxiaoNeural",
        speed: float = 1.0,
        pitch: float = 0,
    ) -> AudioResult:
        """
        生成配音音频。

        :param text: 配音文本
        :param voice_type: 音色
        :param speed: 语速 (0.5-2.0)
        :param pitch: 音调 (-10到10)
        :returns: AudioResult(path, duration, sample_rate)
        """
        ...

    async def generate_audio_async(
        self,
        text: str,
        voice_type: str = "zh-CN-XiaoxiaoNeural",
    ) -> str:
        """异步生成音频（用于Celery任务）"""
        ...

    def get_available_voices(self) -> list[VoiceInfo]:
        """获取可用音色列表"""
        ...
```

### 5.3 ImageService

```python
class ImageService:
    """图片服务"""

    def prepare_scene_images(
        self,
        script_content: dict,
        product_image: str | None = None,
    ) -> list[str]:
        """
        准备场景配图。

        策略：
        1. 优先使用素材库中匹配的图片
        2. 其次使用商品主图
        3. 最后使用AI生成
        """
        ...

    async def generate_scene_image(
        self,
        prompt: str,
        style: str = "product_show",
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """
        AI生成场景配图。

        调用火山引擎文生图API。
        """
        ...

    def get_default_image(
        self,
        category: str,
        scene_type: str,
    ) -> str:
        """获取默认模板图片"""
        ...
```

### 5.4 VideoComposer

```python
class VideoComposer:
    """视频合成服务"""

    def compose(
        self,
        audio_path: str,
        images: list[str],
        subtitles: list[dict],
        output_dir: str,
        output_format: str = "9:16",
        bgm_path: str | None = None,
        transitions: list[str] | None = None,
    ) -> str:
        """
        合成最终视频。

        :param audio_path: 配音音频路径
        :param images: 场景图片路径列表
        :param subtitles: 字幕数据
        :param output_dir: 输出目录
        :param output_format: 输出格式
        :param bgm_path: 背景音乐路径
        :param transitions: 转场效果列表
        :returns: 合成视频的本地路径
        """
        ...

    def compose_scene(
        self,
        scene_data: dict,
        output_path: str,
    ) -> str:
        """
        合成单个分镜。

        用于分镜级干预后的局部重渲染。
        """
        ...

    def concat_scenes(
        self,
        scene_paths: list[str],
        transitions: list[str],
        output_path: str,
    ) -> str:
        """
        拼接多个分镜为完整视频。
        """
        ...
```

### 5.5 FFmpegWrapper

```python
class FFmpegWrapper:
    """FFmpeg封装"""

    def add_audio_to_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """将音频叠加到视频"""
        ...

    def add_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        position: str = "bottom",
    ) -> str:
        """添加字幕"""
        ...

    def add_bgm(
        self,
        video_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.3,
    ) -> str:
        """添加背景音乐"""
        ...

    def apply_transition(
        self,
        video1_path: str,
        video2_path: str,
        output_path: str,
        transition_type: str = "fade",
        duration: float = 0.5,
    ) -> str:
        """应用转场效果"""
        ...

    def convert_format(
        self,
        input_path: str,
        output_path: str,
        resolution: str = "1080x1920",
        quality: str = "high",
    ) -> str:
        """转换视频格式"""
        ...
```

---

## 6. 异步任务编排

### 6.1 Celery任务链

```python
from celery import chain, group

@celery_app.task(bind=True, name="generate_video_task")
def generate_video_task(self, task_id: int):
    """视频生成主任务"""

    # 更新状态
    update_task_status(task_id, "processing", step="tts", progress=0)

    # 任务链
    task_chain = chain(
        step_tts.s(task_id),           # Step 1: TTS配音
        step_images.s(task_id),        # Step 2: 场景配图
        step_compose.s(task_id),       # Step 3: 视频合成
        step_finalize.s(task_id),      # Step 4: 上传+完成
    )
    task_chain.apply_async()


@celery_app.task
def step_tts(task_id: int):
    """Step 1: TTS配音生成"""
    update_task_status(task_id, "processing", step="tts", progress=10)

    task = get_task(task_id)
    script = get_script(task.script_id)
    script_content = json.loads(script.content)

    # 生成配音
    audio_result = tts_service.generate_audio(
        script_content["full_text"],
        voice_type=task.voice_type
    )

    # 上传到MinIO
    audio_url = minio_service.upload(audio_result.path, f"tasks/{task_id}/audio.mp3")

    # 保存素材记录
    save_material(task.project_id, type=3, url=audio_url, duration=audio_result.duration)

    update_task_status(task_id, "processing", step="tts", progress=100)

    return {"audio_url": audio_url, "task_id": task_id}


@celery_app.task
def step_images(task_id: int, tts_result: dict):
    """Step 2: 场景配图"""
    update_task_status(task_id, "processing", step="image", progress=20)

    task = get_task(task_id)
    script = get_script(task.script_id)
    script_content = json.loads(script.content)

    # 准备配图
    image_paths = image_service.prepare_scene_images(
        script_content,
        product_image=task.project.product_image
    )

    # 上传到MinIO
    image_urls = []
    for i, img_path in enumerate(image_paths):
        url = minio_service.upload(img_path, f"tasks/{task_id}/scene_{i}.png")
        image_urls.append(url)

    update_task_status(task_id, "processing", step="image", progress=100)

    return {**tts_result, "image_urls": image_urls}


@celery_app.task
def step_compose(task_id: int, prev_result: dict):
    """Step 3: 视频合成"""
    update_task_status(task_id, "processing", step="compose", progress=30)

    task = get_task(task_id)
    script = get_script(task.script_id)
    script_content = json.loads(script.content)

    # 合成视频
    video_path = video_composer.compose(
        audio_path=download_from_minio(prev_result["audio_url"]),
        images=[download_from_minio(url) for url in prev_result["image_urls"]],
        subtitles=script_content.get("body", []),
        output_dir=f"/tmp/tasks/{task_id}",
        output_format=task.output_format,
    )

    update_task_status(task_id, "processing", step="compose", progress=100)

    return {**prev_result, "video_path": video_path}


@celery_app.task
def step_finalize(task_id: int, prev_result: dict):
    """Step 4: 上传成品+更新状态"""
    update_task_status(task_id, "processing", step="upload", progress=90)

    # 上传到MinIO
    video_url = minio_service.upload(
        prev_result["video_path"],
        f"tasks/{task_id}/output.mp4"
    )

    # 更新任务状态
    update_task_status(
        task_id, "completed",
        progress=100,
        result_video_url=video_url
    )

    # 更新项目状态
    update_project_video(task.project_id, video_url)

    return {"video_url": video_url, "task_id": task_id}
```

### 6.2 进度更新机制

```python
def update_task_status(
    task_id: int,
    status: str,
    step: str | None = None,
    progress: int | None = None,
    error_message: str | None = None,
    result_video_url: str | None = None,
):
    """更新任务状态（同步版本，用于Celery Worker）"""
    with get_sync_db() as db:
        task = db.query(VideoTask).get(task_id)
        task.status = status
        if step:
            task.current_step = step
        if progress is not None:
            task.progress = progress
        if error_message:
            task.error_message = error_message
        if result_video_url:
            task.result_video_url = result_video_url
        if status == "processing" and not task.started_at:
            task.started_at = datetime.utcnow()
        if status in ("completed", "failed"):
            task.completed_at = datetime.utcnow()
        db.commit()

    # 同时更新Celery Task Meta（供前端WebSocket/轮询获取）
    if step and progress is not None:
        current_task.update_state(state='PROGRESS', meta={
            'step': step,
            'progress': progress,
            'status': status,
        })
```

---

## 7. 数据流图

```
┌────────────────────────────────────────────────────────────────────┐
│                       视频生成模块数据流                             │
│                                                                    │
│  POST /api/v1/projects/{id}/video/generate                        │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────────────────────────┐                       │
│  │       VideoGenerationService            │                       │
│  │  ① 创建 video_task 记录                 │                       │
│  │  ② 发送 Celery 任务                     │                       │
│  │  ③ 返回 task_id                         │                       │
│  └────────────────┬────────────────────────┘                       │
│                   │                                                │
│                   ▼                                                │
│  ┌─────────────────────────────────────────┐                       │
│  │       Celery Worker (异步执行)           │                       │
│  │                                         │                       │
│  │  Step 1: TTS 配音生成                    │                       │
│  │    输入：剧本 full_text                   │                       │
│  │    调用：火山引擎 TTS API                 │                       │
│  │    输出：MP3 音频                         │                       │
│  │    上传：MinIO tasks/{id}/audio.mp3      │                       │
│  │    记录：materials(type=3)               │                       │
│  │                                         │                       │
│  │  Step 2: 场景配图准备                    │                       │
│  │    输入：剧本 image_keyword               │                       │
│  │    策略：素材库 > 商品图 > AI生成          │                       │
│  │    调用：火山引擎 文生图 API（可选）       │                       │
│  │    输出：PNG 图片列表                     │                       │
│  │    上传：MinIO tasks/{id}/scene_*.png    │                       │
│  │    记录：materials(type=1)               │                       │
│  │                                         │                       │
│  │  Step 3: 视频合成                        │                       │
│  │    输入：音频 + 图片列表 + 字幕           │                       │
│  │    调用：FFmpeg / MoviePy                │                       │
│  │    处理：                                │                       │
│  │      - 图片按时间轴排列                   │                       │
│  │      - 叠加字幕                          │                       │
│  │      - 混音（配音+BGM）                  │                       │
│  │      - 添加转场                          │                       │
│  │    输出：MP4 视频                         │                       │
│  │                                         │                       │
│  │  Step 4: 上传成品                        │                       │
│  │    上传：MinIO tasks/{id}/output.mp4     │                       │
│  │    更新：video_task.status = completed   │                       │
│  │    更新：project.video_output_url        │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                    │
│  前端轮询 / WebSocket                                              │
│       │                                                            │
│       ▼                                                            │
│  GET /api/v1/video-tasks/{id}/progress                            │
│       → 返回当前步骤 + 进度百分比                                    │
│                                                                    │
│  完成后                                                            │
│       │                                                            │
│       ▼                                                            │
│  GET /api/v1/video-tasks/{id}/preview                             │
│       → 返回视频URL供在线预览                                       │
│                                                                    │
│  POST /api/v1/video-tasks/{id}/export                             │
│       → 导出不同格式/分辨率                                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. 分镜级干预流程

```
┌────────────────────────────────────────────────────────────────────┐
│                       分镜级干预流程                                 │
│                                                                    │
│  POST /api/v1/video-tasks/{id}/scenes/{index}/intervene           │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────────────────────────┐                       │
│  │       干预类型判断                        │                       │
│  │                                         │                       │
│  │  action=replace_image                   │                       │
│  │    → 仅更新该分镜图片                     │                       │
│  │    → 触发该分镜重新合成                   │                       │
│  │                                         │                       │
│  │  action=replace_audio                   │                       │
│  │    → 仅更新该分镜配音                     │                       │
│  │    → 触发该分镜重新合成                   │                       │
│  │                                         │                       │
│  │  action=edit_subtitle                   │                       │
│  │    → 仅更新字幕文本                       │                       │
│  │    → 触发该分镜重新合成                   │                       │
│  │                                         │                       │
│  │  action=change_duration                 │                       │
│  │    → 更新时长，重新计算时间轴              │                       │
│  │    → 触发整片重新合成                     │                       │
│  │                                         │                       │
│  │  action=regenerate                      │                       │
│  │    → 重新生成该分镜的所有素材              │                       │
│  │    → 触发该分镜重新合成                   │                       │
│  └────────────────┬────────────────────────┘                       │
│                   │                                                │
│                   ▼                                                │
│  ┌─────────────────────────────────────────┐                       │
│  │       局部重渲染                          │                       │
│  │                                         │                       │
│  │  1. 更新 video_compositions 表           │                       │
│  │  2. 仅重渲染受影响的分镜                   │                       │
│  │  3. 拼接所有分镜为完整视频                 │                       │
│  │  4. 上传新成品                           │                       │
│  │  5. 更新任务状态                          │                       │
│  └─────────────────────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 9. 状态流转

### 9.1 视频任务状态

```
pending ──→ processing ──→ completed
   │            │              │
   │            ├──→ failed    │
   │            │      │       │
   │            │      ▼       │
   │            │   retrying   │
   │            │      │       │
   │            │      └───────┘
   │            │
   └──→ cancelled
```

| 状态 | 含义 |
|---|---|
| pending | 任务已创建，等待执行 |
| processing | 正在执行（含子状态） |
| completed | 已完成 |
| failed | 失败（记录错误信息） |
| retrying | 重试中 |
| cancelled | 已取消 |

### 9.2 processing 子状态

| 子状态 | 含义 | 进度范围 |
|---|---|---|
| tts | TTS配音生成中 | 0-30% |
| image | 场景配图准备中 | 30-60% |
| compose | 视频合成中 | 60-90% |
| upload | 上传成品中 | 90-100% |

---

## 10. 异常处理与重试

### 10.1 重试策略

| 步骤 | 重试次数 | 重试间隔 | 降级策略 |
|---|---|---|---|
| TTS | 3次 | 1s/2s/4s | 使用Edge TTS |
| 文生图 | 2次 | 2s/4s | 使用默认图片 |
| 视频合成 | 1次 | - | 标记失败 |
| MinIO上传 | 3次 | 1s/2s/4s | 标记失败 |

### 10.2 错误码

| 错误码 | 含义 |
|---|---|
| V010001 | TTS生成失败 |
| V010002 | 图片生成失败 |
| V010003 | 视频合成失败 |
| V010004 | 上传失败 |
| V010005 | 素材下载失败 |
| V010006 | 格式转换失败 |
| V010007 | 任务超时 |
| V010008 | 任务被取消 |

---

## 11. 目录结构规划

```
backend/app/
├── api/v1/
│   └── video.py                   # 视频生成 API 路由
├── models/
│   └── video_task.py              # VideoTask ORM 模型
│   └── video_composition.py       # VideoComposition ORM 模型
├── schemas/
│   └── video.py                   # 视频请求/响应模型
├── services/
│   ├── video_generation.py        # 视频生成调度服务（已有，需扩展）
│   ├── tts_service.py             # TTS服务（已有，需接入真实API）
│   ├── image_service.py           # 图片服务（已有，需接入真实API）
│   ├── video_composer.py          # 视频合成服务（已有，需接入FFmpeg）
│   └── ffmpeg_wrapper.py          # FFmpeg封装
├── workers/
│   └── video_tasks.py             # Celery任务（已有，需扩展）
└── core/
    └── ffmpeg_client.py           # FFmpeg初始化
```

---

## 12. 实现顺序

| 阶段 | 任务 | 产出 | 依赖 |
|---|---|---|---|
| **Phase 1** | TTS服务接入（火山引擎） | 可生成配音 | TTS API |
| **Phase 2** | FFmpeg视频合成 | 基础合成能力 | FFmpeg |
| **Phase 3** | 任务状态追踪 | 进度可查询 | Redis |
| **Phase 4** | 场景配图服务 | 智能配图 | 图片API |
| **Phase 5** | 分镜级干预 | 局部重渲染 | Phase 2 |
| **Phase 6** | 多格式导出 | 适配多端 | Phase 2 |
| **Phase 7** | BGM+转场 | 视觉增强 | Phase 2 |

---

## 13. 注意事项

1. **FFmpeg依赖**：服务器需安装FFmpeg，Dockerfile中需包含
2. **GPU加速**：视频合成可利用GPU加速，需配置CUDA
3. **临时文件清理**：任务完成后清理/tmp下的中间文件
4. **并发控制**：视频合成是CPU密集型，Worker并发数应控制
5. **超时处理**：单个任务设置最大执行时间（如5分钟）
6. **内存管理**：大视频处理时注意内存占用，考虑分段合成
7. **编码规范**：统一使用H.264编码，确保兼容性
