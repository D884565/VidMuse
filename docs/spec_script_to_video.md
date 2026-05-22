# 剧本生成 → 视频生成 开发规格说明书

## 1. 概述

本模块负责 AIGC 带货视频生成的**核心链路**：根据用户提交的商品信息，AI 自动生成带货文案剧本，再合成为视频成品。

### 1.1 所属链路位置

```
用户提交商品 ──→ [剧本生成] ──→ [视频生成] ──→ 返回成品
   (前端)       本模块范围        本模块范围      (前端播放)
```

### 1.2 涉及的外部依赖

| 依赖 | 用途 |
|---|---|
| OpenAI API | LLM 生成带货文案 |
| MySQL | 存储项目、剧本、素材记录 |
| MinIO | 存储素材图片、成品视频 |
| Redis | Celery 任务队列 |
| ChromaDB | 商品知识库向量检索（RAG） |

---

## 2. 数据库表结构

基于现有的 `init.sql`，补充完整。项目表和剧本表已定义，素材表需要补充字段。

### 2.1 projects 表（已定义）

```sql
CREATE TABLE projects (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    title            VARCHAR(200) NOT NULL COMMENT '项目标题',
    description      TEXT COMMENT '项目描述',
    product_url      VARCHAR(1000) COMMENT '商品链接',
    product_image    VARCHAR(500) COMMENT '商品主图URL',
    product_info     TEXT COMMENT '商品信息解析结果（JSON：标题/价格/卖点）',
    video_output_url VARCHAR(500) COMMENT '最终成片URL（MinIO路径）',
    status           VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT '状态：draft/processing/completed/failed',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频项目表';
```

> **说明：** 相比原 SQL，新增了 `status` 字段用于跟踪项目状态流转。

### 2.2 scripts 表（已定义）

```sql
CREATE TABLE scripts (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT NOT NULL COMMENT '所属项目',
    title            VARCHAR(200) COMMENT '剧本标题',
    content          TEXT NOT NULL COMMENT '剧本内容（JSON 结构，见下文）',
    target_duration  INT COMMENT '目标时长(秒)',
    ai_model         VARCHAR(50) COMMENT '使用的AI模型',
    ai_prompt        TEXT COMMENT '生成使用的完整Prompt',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='剧本表';
```

#### 剧本 content 的 JSON 结构

```json
{
  "opening": "前3秒吸引注意的开场白",
  "body": [
    {
      "scene": 1,
      "text": "详细卖点讲解段落1",
      "duration_sec": 5,
      "image_keyword": "产品功能场景描述",
      "tts_audio_url": null
    },
    {
      "scene": 2,
      "text": "详细卖点讲解段落2",
      "duration_sec": 5,
      "image_keyword": "使用效果场景描述",
      "tts_audio_url": null
    }
  ],
  "closing": "引导下单的结尾话术",
  "full_text": "完整的纯文本版本（用于 TTS）"
}
```

### 2.3 materials 表（需补充）

```sql
CREATE TABLE materials (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT COMMENT '所属项目（NULL表示通用素材）',
    script_id        BIGINT COMMENT '所属剧本段落',
    type             TINYINT NOT NULL COMMENT '素材类型：1=商品图 2=背景音乐 3=配音音频 4=字幕 5=成品视频',
    title            VARCHAR(200) COMMENT '素材标题',
    url              VARCHAR(500) NOT NULL COMMENT '存储URL（MinIO路径）',
    file_size        BIGINT COMMENT '文件大小(字节)',
    duration         INT COMMENT '时长(秒)，音视频素材',
    format           VARCHAR(20) COMMENT '文件格式：mp4/mp3/wav/png/jpg',
    ai_features      JSON COMMENT 'AI特征（预留）',
    source_type      TINYINT DEFAULT 0 COMMENT '来源：0=用户上传 1=AI生成 2=系统模板',
    scene_index      INT COMMENT '所属场景序号（对应剧本body.scene）',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='素材表';
```

---

## 3. 数据流图

```
┌──────────────────────────────────────────────────────────────────┐
│                  剧本生成 → 视频生成 完整链路                       │
│                                                                  │
│  POST /api/v1/projects/{id}/generate                             │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────┐                     │
│  │          ScriptGenerationService        │                     │
│  │                                         │                     │
│  │  ① 从 MySQL 读取 project 的商品信息        │                     │
│  │  ② 从 ChromaDB 检索商品相关知识点（RAG）  │                     │
│  │  ③ 构造 Prompt → 调用 LLM 生成剧本       │                     │
│  │  ④ 解析 LLM 返回的 JSON 结构             │                     │
│  │  ⑤ 剧本写入 MySQL scripts 表             │                     │
│  │  ⑥ 更新 project 状态为 script_ready      │                     │
│  └──────────────┬──────────────────────────┘                     │
│                 │                                                 │
│                 ▼ (同一请求内同步完成，或异步)                       │
│  ┌─────────────────────────────────────────┐                     │
│  │          VideoGenerationService         │                     │
│  │                                         │                     │
│  │  ⑦ 发送 Celery 任务到 Redis 队列          │                     │
│  │  ⑧ 更新 project 状态为 processing        │                     │
│  │  ⑨ 返回 project_id + "任务已提交"         │                     │
│  └──────────────────────────────────────────┘                    │
│                                                                  │
│  ┌──────────────── Celery Worker ──────────────────────────┐     │
│  │                                                          │     │
│  │  Step 1: TTS 生成配音音频                                  │     │
│  │    输入：剧本 full_text                                   │     │
│  │    输出：MP3 文件 → MinIO                                  │     │
│  │    入库：materials(type=3, script_id)                      │     │
│  │                                                          │     │
│  │  Step 2: 获取场景配图                                       │     │
│  │    从 project.product_image 或 LLM 描述关键词生成/搜索      │     │
│  │    入库：materials(type=1, scene_index)                    │     │
│  │                                                          │     │
│  │  Step 3: 合成视频                                          │     │
│  │    输入：配音音频 + 场景图片 + 字幕文字                       │     │
│  │    处理：图片按时间轴排列 → 叠加字幕 → 混音                   │     │
│  │    输出：MP4 文件 → MinIO                                   │     │
│  │    入库：materials(type=5)                                 │     │
│  │                                                          │     │
│  │  Step 4: 更新项目状态                                       │     │
│  │    project.video_output_url = MinIO 视频链接                 │     │
│  │    project.status = completed                               │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                  │
│  前端轮询 GET /api/v1/projects/{id}                                │
│       → status = completed → 展示视频                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. API 接口定义

### 4.1 提交生成任务

```
POST /api/v1/projects/{project_id}/generate
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| project_id | path | 是 | 项目ID |
| target_duration | int | 否 | 目标视频时长（秒），默认30 |
| voice_type | str | 否 | TTS 音色，默认 "zh-CN-XiaoxiaoNeural" |

**响应：**

```json
{
  "code": "0000000",
  "message": "任务已提交",
  "data": {
    "project_id": 1,
    "script_id": 1,
    "status": "processing"
  }
}
```

### 4.2 查询项目状态

```
GET /api/v1/projects/{project_id}
```

**响应：**

```json
{
  "code": "0000000",
  "message": "操作成功",
  "data": {
    "id": 1,
    "title": "xxx商品带货视频",
    "status": "completed",
    "video_url": "http://minio:9000/aigc-videos/projects/1/output.mp4",
    "script": {
      "id": 1,
      "content": { "...剧本JSON..." }
    },
    "materials": [
      { "type": 3, "url": "...", "duration": 30 },
      { "type": 5, "url": "...", "duration": 30 }
    ],
    "created_at": "2026-05-21T10:00:00"
  }
}
```

### 4.3 重新生成剧本

```
POST /api/v1/projects/{project_id}/regenerate-script
```

覆盖当前剧本，重新调用 LLM 生成。

---

## 5. Service 层接口定义

### 5.1 ScriptGenerationService

```python
class ScriptGenerationService:
    """剧本生成服务"""

    async def generate_script(
        self,
        project_id: int,
        target_duration: int = 30,
        voice_type: str = "zh-CN-XiaoxiaoNeural"
    ) -> ScriptGenerateResult:
        """
        生成带货剧本。

        流程：
        1. 从 MySQL 读取 project 信息（含 product_info）
        2. 从 ChromaDB 检索相关商品知识
        3. 构造 Prompt 调用 LLM
        4. 解析 LLM 返回的 JSON 结构
        5. 保存到 MySQL scripts 表
        6. 返回 script_id
        """
        ...

    async def retrieve_product_knowledge(
        self,
        product_info: dict
    ) -> list[str]:
        """
        从 ChromaDB 检索商品相关知识点。
        用于 RAG，增强LLM生成质量。
        """
        ...

    def build_generation_prompt(
        self,
        product_info: dict,
        knowledge: list[str],
        target_duration: int
    ) -> str:
        """构造 LLM Prompt"""
        ...
```

### 5.2 VideoGenerationService

```python
class VideoGenerationService:
    """视频生成服务（调度层）"""

    async def submit_generation_task(
        self,
        project_id: int,
        script_id: int
    ) -> TaskSubmitResult:
        """
        提交视频生成异步任务到 Celery。

        1. 更新 project 状态为 processing
        2. 发送 Celery 任务
        3. 返回任务信息
        """
        ...

    async def get_project_detail(
        self,
        project_id: int
    ) -> ProjectDetail:
        """
        查询项目详情（含剧本、素材、状态）。
        供前端轮询使用。
        """
        ...
```

### 5.3 Celery Worker 任务（核心）

```python
@celery_app.task(bind=True, max_retries=3)
def generate_video_task(self, project_id: int, script_id: int):
    """视频生成异步任务（LangGraph 编排）"""
    ...

    # Step 1: TTS 生成配音
    tts_result = tts_service.generate_audio(script_content)

    # Step 2: 获取/处理场景图片
    images = image_service.prepare_scene_images(script_content)

    # Step 3: 视频合成
    video_path = video_composer.compose(
        audio=tts_result.audio_path,
        images=images,
        subtitles=script_content.body,
        output_dir=f"projects/{project_id}/"
    )

    # Step 4: 上传 MinIO 并更新状态
    video_url = minio_service.upload(video_path, f"projects/{project_id}/output.mp4")
    project_service.update_video_result(project_id, video_url, "completed")
```

---

## 6. 关键接口合约

### 6.1 LLM 剧本生成 Prompt 模板

```
你是一个带货视频编剧。根据以下商品信息，生成一个{target_duration}秒的带货短视频剧本。

商品信息：
{product_info}

参考知识：
{knowledge}

请严格按以下 JSON 格式输出：
{
  "opening": "吸引人的开场白",
  "body": [{ "scene": 1, "text": "卖点1", "image_keyword": "配图描述" }],
  "closing": "引导下单结尾",
  "full_text": "完整配音文本"
}
```

### 6.2 统一响应格式（现有框架）

```python
Response.success(data={...})
Response.error(code="A050002", message="视频生成失败")
```

### 6.3 异常码（已有）

| 错误码 | 含义 |
|---|---|
| A030002 | AI 生成失败 |
| A030003 | 提示词过长 |
| A050001 | 视频生成模块错误 |
| A050002 | 视频生成失败 |
| A050003 | 视频渲染失败 |
| A050004 | 视频时长过长 |
| A050005 | 模板不存在 |
| A050006 | 素材不存在 |

---

## 7. 目录结构规划

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── generation.py       ← 生成相关路由
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py              ← Project ORM 模型
│   │   ├── script.py               ← Script ORM 模型
│   │   └── material.py             ← Material ORM 模型
│   ├── schemas/
│   │   ├── project.py              ← Project Pydantic 模型
│   │   ├── script.py
│   │   └── generation.py           ← 生成请求/响应模型
│   ├── services/
│   │   ├── script_generation.py    ← 剧本生成服务
│   │   ├── video_generation.py     ← 视频生成调度
│   │   ├── tts_service.py          ← 语音合成
│   │   ├── image_service.py        ← 图片处理
│   │   ├── video_composer.py       ← 视频合成
│   │   └── minio_service.py        ← MinIO 文件操作
│   ├── core/
│   │   ├── config.py               ← 配置管理
│   │   ├── database.py             ← 数据库连接
│   │   ├── celery_app.py           ← Celery 初始化
│   │   └── minio_client.py         ← MinIO 客户端
│   └── workers/
│       └── video_tasks.py          ← Celery 任务定义
├── alembic/                        ← 数据库迁移
│   └── versions/
└── tests/
    ├── test_script_generation.py
    ├── test_video_generation.py
    └── test_video_composer.py
```

---

## 8. 状态流转

```
draft ──→ script_ready ──→ processing ──→ completed
                 │                            │
                 └──→ failed                  └──→ failed
```

| 状态 | 含义 |
|---|---|
| draft | 项目创建，信息待完善 |
| script_ready | 剧本已生成，等待视频制作 |
| processing | 视频正在生成（Celery 执行中） |
| completed | 视频生成完成 |
| failed | 失败（含失败原因记录） |

---

## 9. 实现顺序

| 阶段 | 任务 | 产出 |
|---|---|---|
| **Phase 1** | 搭建项目目录结构 + 数据库 Model + Alembic 迁移 | 基础代码框架 |
| **Phase 2** | 实现 LLM 剧本生成（ScriptGenerationService） | 可生成带货文案 |
| **Phase 3** | 实现 TTS 语音合成 + MinIO 上传 | 音频素材入库 |
| **Phase 4** | 实现视频合成（VideoComposer） | 可产出 MP4 |
| **Phase 5** | 接入 Celery 任务编排 + 状态管理 | 全链路跑通 |
| **Phase 6** | API 路由 + 异常处理 + 前端联调 | 完整可调用 |

---

## 10. 注意事项

1. **LLM 输出解析** — LLM 返回可能不是合法 JSON，需做容错处理（正则提取 + 默认值兜底）
2. **大视频处理** — 超过 60s 的视频建议拆段合成再拼接，避免内存占用过高
3. **失败重试** — Celery 任务需支持重试机制，每个步骤失败应有明确错误记录
4. **文件清理** — 临时文件（下载的素材、中间音频等）在任务完成后清理
5. **并发限制** — 视频合成是 CPU/GPU 密集型，Worker 并发数应根据机器配置控制
