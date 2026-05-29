# 电商 AIGC 带货视频生成系统个人负责模块改进建议

## 1. 文档定位

本项目整体目标是面向商家的 AIGC 带货视频生成系统。根据当前分工，RAG 检索、素材向量化、素材结构化检索等能力由搭档负责；本文只整理“用户登录、项目创建、剧本生成、分镜管理、视频生成、任务进度、预览导出”等非 RAG 部分的优化方向。

本文中的 RAG 只作为外部依赖出现：你的模块需要定义清晰的调用边界、降级策略和数据字段，但不展开检索算法、Embedding、向量库、素材切片解析等实现。

## 2. 你负责的主链路

当前主链路可以拆成以下几段：

```text
用户登录
  -> 创建项目
  -> 商品链接抓取或商品信息录入
  -> 生成剧本与基础分镜
  -> 提交视频生成任务
  -> TTS / 图片生成 / 视频片段生成 / 合成
  -> 任务进度查询
  -> 分镜级调整或重生成
  -> 预览与导出
```

相关代码位置：

- 登录与鉴权：`backend/v1/app/user`、`frontend/src/pages/Login.jsx`、`frontend/src/services/auth.js`、`frontend/src/services/api.js`
- 项目创建：`backend/v1/app/generate/controller/generation.py`、`backend/v1/app/generate/service/project_service.py`、`frontend/src/services/project.js`
- 商品抓取：`backend/v1/app/product/service/product_crawl_service.py`
- 剧本生成：`backend/v1/app/generate/service/script_generation.py`
- 分镜与对话式调整：`backend/v1/app/generate/service/chat_service.py`
- 视频生成调度：`backend/v1/app/generate/service/video_generation.py`
- Celery 视频任务：`backend/v1/app/generate/temp/video_tasks.py`
- TTS / 图片 / 视频 / 合成：`backend/v1/app/generate/service/tts_service.py`、`image_generation_service.py`、`video_composer.py`
- 前端生成体验：`frontend/src/components/Chat`、`frontend/src/components/Keyframes`、`frontend/src/hooks/useProjectPolling.js`

## 3. 和 RAG 模块的协作边界

为了避免职责混在一起，建议把 RAG 当成一个可替换服务：

```text
你的模块输入：project_id、product_info、user_prompt、frame 信息
RAG 模块输出：参考素材、参考脚本、素材 slice、标签、相似度、来源信息
你的模块消费：把 RAG 结果放入 Prompt、分镜候选素材、生成 trace、素材来源声明
```

你这边需要做的不是实现检索，而是保证调用接口稳定：

- RAG 可用时：剧本 Prompt 能融合 `reference_scripts`、`reference_assets`、`product_knowledge`。
- RAG 不可用时：系统仍可根据商品信息和用户 Prompt 生成剧本并出片。
- RAG 返回为空时：前端给出“未召回素材，已使用商品主图/AI 生成兜底”的可解释提示。
- RAG 返回素材时：记录素材 ID、slice ID、source、score，便于后续预览、替换和合规声明。

建议和搭档约定一个最小响应结构：

```json
{
  "items": [
    {
      "id": "asset_or_slice_id",
      "type": "image|video|slice|script|knowledge",
      "title": "string",
      "summary": "string",
      "url": "string",
      "score": 0.87,
      "source": "upload|public_reference|generated",
      "tags": ["close_up", "product_detail"],
      "metadata": {}
    }
  ]
}
```

## 4. 用户登录与鉴权改进

### 当前可优化点

- 前端已通过 Axios 拦截器注入 token，并支持 refresh token，但登录态恢复、错误提示、接口权限边界还可以更清晰。
- 后端项目接口已使用 `get_current_user_id`，但素材模块里仍有固定 user_id 的遗留写法。虽然素材/RAG 不是你的主要职责，但你的项目创建和详情查询必须保证只返回当前用户数据。
- 前端页面刷新后的用户状态恢复依赖 `getUserInfo()`，需要明确 loading 状态，避免短暂闪回登录页。

### 建议改进

1. 登录态前端体验

- 在 `MainLayout` 或全局入口增加 `authLoading` 状态，避免刷新页面时先渲染 Login 再跳回主页面。
- 登录失败时区分“账号密码错误”“token 过期”“网络异常”“服务端错误”。
- refresh token 失败时统一清理 token、user、当前项目状态。

2. 后端鉴权一致性

- 所有 `/generate/v1/projects`、`/chat`、`/frames`、`/export` 接口都必须校验 `project.user_id == current_user_id`。
- 任务查询接口不能只按 task_id 查询，必须同时校验 task 对应 project 是否属于当前用户。
- 生成结果 Asset 入库时使用 `project.user_id`，不要使用固定用户 ID。

3. 权限与审计字段

建议给关键表补充：

```text
created_by
updated_by
deleted_at
last_opened_at
```

最小可行版本可以先只加 `deleted_at`，支持项目软删除，避免误删后无法恢复。

## 5. 项目创建流程改进

### 当前流程

当前 `POST /generate/v1/projects` 会完成：

```text
创建 Project
  -> 可选抓取商品信息
  -> 同步生成剧本
  -> 提交 Celery 视频任务
  -> 返回项目状态
```

这个流程适合 Demo，但真实长任务里有两个问题：

- 创建项目接口耗时不可控，商品抓取和剧本生成失败会影响创建体验。
- 项目创建、剧本生成、视频生成三个动作耦合太紧，用户没有机会先检查项目输入和剧本。

### 建议改进成三段式

```text
Step 1: 创建项目
  -> 只保存标题、商品链接、用户 Prompt、目标时长、风格等基础信息

Step 2: 生成剧本
  -> 可异步执行，成功后进入 script_ready

Step 3: 一键成片
  -> 用户确认剧本后提交 render task
```

建议接口：

```text
POST /generate/v1/projects
POST /generate/v1/projects/{project_id}/script/generate
POST /generate/v1/projects/{project_id}/render
GET  /generate/v1/projects/{project_id}
```

为了不破坏现有“一键成片”体验，可以保留 `auto_render=true`：

```json
{
  "title": "商品标题",
  "product_url": "https://...",
  "user_prompt": "夏日度假风，突出便携",
  "target_duration": 15,
  "auto_render": true
}
```

### 项目状态建议

当前状态有 `draft/script_ready/processing/completed/failed`，建议细化为：

```text
draft              项目已创建，未生成剧本
product_ready      商品信息已抓取或已录入
script_generating  剧本生成中
script_ready       剧本可编辑
render_queued      视频生成排队中
rendering          视频生成中
review_required    生成结果需要用户确认或审核
completed          成片完成
failed             失败
cancelled          用户取消
```

前端可以只展示较少文案，但后端状态更细会方便定位问题。

## 6. 商品信息与项目输入改进

### 当前可优化点

- 商品抓取失败后会继续创建项目，这是对的，但前端需要明确告诉用户“抓取失败，已进入手动补充模式”。
- `product_info` 现在以 JSON 字符串存在 `projects` 表中，短期可用，但后续会影响字段查询和复用。
- 用户输入字段已经包含 `style`、`target_audience`、`key_points`、`avoid`、`rag_weight`、`target_duration`、`voice_type`，但前端需要更明确地组织这些输入。

### 建议改进

1. 项目创建表单拆成基础信息和高级设置

基础信息：

- 商品链接或商品主图。
- 商品标题。
- 核心卖点。
- 目标人群。
- 生成目标，比如“提升点击”“突出价格”“讲清使用方法”。

高级设置：

- 视频风格。
- 目标时长。
- 画幅。
- 配音音色。
- 禁止内容。
- 是否自动出片。

2. 商品抓取结果可编辑

商品抓取后不要直接进入生成，可以先展示：

- 标题。
- 价格。
- 商品主图。
- 规格。
- 卖点摘要。
- 用户可勾选保留哪些卖点进入剧本。

3. 商品信息存储

短期可以继续用 `project.product_info`，但建议增加结构化字段或独立 `products` 表：

```text
products
- id
- user_id
- title
- description
- product_url
- price
- original_price
- category
- main_images
- specs
- source_platform
- crawl_status
- crawl_error
```

这样项目可以关联 `product_id`，一个商品可以生成多条视频。

## 7. 剧本生成与分镜管理改进

### 当前可优化点

- 当前剧本直接写入 `frames`，缺少完整剧本版本实体。
- LLM 返回 JSON 后虽然做了基础字段检查，但没有完整 Schema 校验和自动修复。
- 分镜内容、配音文案、字幕、镜头运动都混在 `Frame` 字段和 `ai_params` 中，后续前端编辑会不够稳定。
- 对话式修改会自动触发重新生成视频，容易导致长任务浪费。

### 建议数据结构

新增 `scripts` 表保存完整剧本版本：

```text
scripts
- id
- project_id
- version
- status
- generation_mode
- prompt_snapshot
- rag_snapshot
- content
- parent_id
- created_at
```

`frames` 保存当前可编辑分镜：

```text
frames
- id
- project_id
- script_id
- sequence
- scene_type
- narration
- image_prompt
- video_prompt
- subtitle_text
- subtitle_position
- duration
- camera
- mood
- selected_asset_id
- selected_slice_id
- image_url
- video_segment_url
- audio_url
- status
- error_message
```

如果短期不改表，至少可以在 `ai_params` 中规范字段：

```json
{
  "narration": "配音文案",
  "camera": "push_in",
  "mood": "warm",
  "subtitle": {
    "text": "限时优惠",
    "position": "bottom",
    "style": "price_tag"
  },
  "source": {
    "asset_id": null,
    "slice_id": null,
    "rag_score": null
  }
}
```

### LLM 输出校验

建议在 `script_generation.py` 中增加三层校验：

1. JSON 提取

- 支持 ```json 包裹。
- 支持模型输出前后带解释文字时提取第一个 JSON 对象。
- 解析失败时记录原始输出，方便排查。

2. Schema 校验

- `video_meta` 必须存在。
- `scenes` 必须是 3 到 5 个。
- 总时长不超过 15 秒或按课题要求限制。
- 每个 scene 必须有 `type`、`duration`、`text`、`visual.image_prompt`、`visual.video_prompt`。

3. 自动修复

- 缺 `video_prompt` 时用 `image_prompt + camera` 兜底。
- 缺 `overlay.text` 时从 narration 中提取短字幕。
- 总时长超过限制时按比例压缩每个分镜时长。
- scene 数量过少时补 CTA，过多时合并 detail 分镜。

### 分镜编辑流程

建议把分镜修改拆成“保存脚本”和“重生成视频”两个动作：

```text
用户修改分镜
  -> 保存 frame 草稿
  -> 标记该 frame dirty
  -> 用户点击重新生成
  -> 只对 dirty frames 提交局部任务
```

前端每个分镜建议支持：

- 修改配音文案。
- 修改字幕。
- 修改画面 Prompt。
- 修改镜头运动。
- 修改时长。
- 重新生成图片。
- 重新生成该分镜视频。
- 恢复上一个版本。

## 8. 视频生成任务改进

### 当前可优化点

- `submit_generation_task()` 只把项目状态改为 `processing`，没有返回 Celery task id。
- Celery Worker 每一步没有持久化进度，前端只能轮询 Project。
- 失败后会将项目置为 `failed` 并重试，但用户不知道失败在哪一步。
- 分镜失败会生成 placeholder 视频，适合兜底，但必须暴露给前端，否则会误以为生成成功。

### 建议新增任务表

```text
generation_tasks
- id
- project_id
- celery_task_id
- task_type          script|render|export|frame_regenerate
- status             queued|running|succeeded|failed|cancelled
- progress           0-100
- current_step
- current_frame_id
- retry_count
- error_code
- error_message
- trace_id
- created_at
- started_at
- finished_at
```

```text
generation_task_steps
- id
- task_id
- step_name
- frame_id
- status
- progress
- input_snapshot
- output_snapshot
- error_message
- started_at
- finished_at
```

### 任务步骤建议

```text
PROJECT_VALIDATION      校验项目、用户、分镜
RAG_REFERENCES_READY    等待或读取 RAG 结果，可跳过
TTS_GENERATING          生成项目级和分镜级配音
IMAGE_GENERATING        生成分镜图
VIDEO_GENERATING        生成分镜视频片段
SEGMENT_COMPOSING       拼接分镜片段
AUDIO_MIXING            合并配音和 BGM
SUBTITLE_RENDERING      叠加字幕
OUTPUT_UPLOADING        上传成片
ASSET_RECORDING         结果入库
COMPLETED               完成
```

注意：`RAG_REFERENCES_READY` 只是你这边的消费步骤，不实现检索。

### 任务 API 建议

```text
POST /generate/v1/projects/{project_id}/render
GET  /generate/v1/tasks/{task_id}
GET  /generate/v1/tasks/{task_id}/steps
POST /generate/v1/tasks/{task_id}/retry
POST /generate/v1/tasks/{task_id}/cancel
```

前端拿到 `task_id` 后轮询任务，而不是只轮询项目。

### 局部重生成

当前接口已有：

```text
POST /generate/v1/projects/{project_id}/frames/{frame_id}/regenerate
POST /generate/v1/projects/{project_id}/frames/{frame_id}/regenerate-image
```

建议补充：

```text
POST /generate/v1/projects/{project_id}/frames/{frame_id}/render
POST /generate/v1/projects/{project_id}/frames/{frame_id}/tts
POST /generate/v1/projects/{project_id}/frames/{frame_id}/replace-asset
```

局部任务规则：

- 只改 Prompt：重跑图片、分镜视频、最终合成。
- 只改台词：重跑该分镜 TTS、最终合成。
- 只改时长：重跑该分镜视频裁剪/补时、最终合成。
- 只换素材：重跑该分镜视频或剪辑、最终合成。

## 9. TTS、字幕、BGM 与合成改进

### TTS

当前已有项目级 TTS 和分镜级 TTS 的雏形。建议：

- 优先使用分镜级 TTS，方便单帧改台词后局部重生成。
- 保存每个 frame 的 `audio_url`、`audio_duration`、`voice_type`。
- TTS 失败时可降级为无配音视频，但前端必须展示“配音生成失败”。

### 字幕

建议从 `frame.text_overlay` 升级为两个概念：

- `subtitle_text`：配音字幕，通常和 narration 一致或精简。
- `sticker_text`：营销贴片，比如“限时优惠”“3 秒看懂”。

字幕生成和渲染建议：

- 后端生成 SRT 或 ASS 字幕文件。
- FFmpeg 叠加字幕。
- 前端可编辑字幕内容、位置和样式。

### BGM

当前 BGM 代码处于保留状态，建议先做简单可控版本：

- 内置 5 到 10 个 BGM 风格枚举：轻快、科技、治愈、紧张、夏日、优雅。
- 前端选择 BGM 风格和音量。
- 后端先从系统素材库选 BGM，不急着做 AI 音乐生成。
- 合成时支持 `bgm_volume` 和 `original_volume`。

### 合成输出

建议导出支持：

```text
9:16  1080x1920 TikTok / Shorts / Reels
16:9  1920x1080 YouTube / 横版投放
1:1   1080x1080 商品 Feed
```

最小实现可以先基于 FFmpeg 做 resize、pad、crop。

## 10. 前端体验改进

### 工作台结构

建议从“聊天入口为主”升级为“项目工作台”：

```text
左侧：项目列表、创建项目
中间：当前项目预览、分镜时间轴
右侧：参数面板、任务进度、生成日志
底部：输入框或快捷操作
```

用户应该能一眼知道：

- 当前项目是什么商品。
- 当前处于哪一步。
- 剧本是否已生成。
- 视频是否正在生成。
- 哪个分镜失败。
- 成片在哪里预览和导出。

### 创建项目弹窗

建议字段：

- 商品链接。
- 商品标题。
- 核心卖点。
- 目标人群。
- 视频目标。
- 风格。
- 时长。
- 画幅。
- 配音。
- 是否自动生成视频。

创建后建议进入项目详情页，而不是只在聊天里返回消息。

### 任务进度组件

进度组件要展示：

- 总进度百分比。
- 当前步骤。
- 当前分镜。
- 已完成步骤。
- 失败步骤。
- 重试按钮。
- 查看详情按钮。

建议文案示例：

```text
正在生成第 2/4 个分镜视频
已完成：剧本、配音、图片
当前：视频片段生成
预计还需：约 2 分钟
```

### 分镜编辑器

建议每个分镜卡片包含：

- 分镜序号。
- 时长。
- 场景类型。
- 预览图或视频片段。
- 配音文案。
- 字幕。
- 画面 Prompt。
- 素材来源。
- 状态：未生成、生成中、完成、失败、已修改待重生成。

快捷操作：

- 编辑文案。
- 编辑画面。
- 重生成图片。
- 重生成视频。
- 重配音。
- 删除分镜。
- 上移/下移。

### 预览与导出

建议预览区支持：

- 当前成片播放。
- 分镜片段播放。
- 音频开关。
- 重新生成。
- 导出画幅选择。
- 下载按钮。

导出失败时不要只提示“失败”，需要显示：

```text
导出失败：字幕渲染失败
建议：检查字幕是否包含特殊字符，或点击重试
```

## 11. 可观测性与错误处理

你负责的视频生成链路是长链路，最容易在答辩时出问题，所以建议重点补可观测性。

### 日志

每个请求和任务都带：

```text
trace_id
user_id
project_id
task_id
frame_id
step_name
model_name
duration_ms
```

### 错误码

建议区分：

```text
PROJECT_NOT_FOUND
PROJECT_FORBIDDEN
PRODUCT_CRAWL_FAILED
SCRIPT_GENERATION_FAILED
SCRIPT_JSON_INVALID
TTS_FAILED
IMAGE_GENERATION_FAILED
VIDEO_GENERATION_FAILED
COMPOSE_FAILED
UPLOAD_FAILED
EXPORT_FAILED
```

### 前端错误展示

前端需要把错误转化为用户能理解的操作建议：

- 商品抓取失败：请手动补充商品标题和卖点。
- 剧本生成失败：请减少约束或稍后重试。
- 图片生成失败：可修改画面描述后重试。
- 视频生成失败：可只重试失败分镜。
- 合成失败：可重新导出。

## 12. 和搭档的接口协作清单

你可以和负责 RAG 的搭档约定以下交付边界：

1. 剧本生成前

你的模块提供：

```json
{
  "project_id": 1,
  "product_title": "string",
  "product_info": {},
  "user_prompt": "string",
  "target_audience": "string",
  "style": "string"
}
```

RAG 返回：

```json
{
  "reference_scripts": [],
  "reference_assets": [],
  "product_knowledge": []
}
```

2. 分镜生成后

你的模块提供：

```json
{
  "project_id": 1,
  "frames": [
    {
      "frame_id": 10,
      "scene_type": "selling_point",
      "description": "string",
      "duration": 3
    }
  ]
}
```

RAG 返回：

```json
{
  "frame_matches": [
    {
      "frame_id": 10,
      "asset_id": 22,
      "slice_id": 31,
      "url": "https://...",
      "score": 0.91,
      "reason": "商品细节特写，适合卖点分镜"
    }
  ]
}
```

3. 生成 trace

你的模块保存 RAG 返回快照，但不负责解释检索算法：

```json
{
  "rag_snapshot": {
    "request_id": "rag_xxx",
    "items_count": 5,
    "used_items": [22, 31]
  }
}
```

## 13. 推荐落地优先级

### 第一阶段：把 P0 做稳

目标：登录后可创建项目，可稳定生成 15 秒以内视频，可看进度，可预览导出。

建议任务：

1. 修复登录态刷新闪烁和 token 过期体验。
2. 项目创建和视频生成拆成“创建项目、生成剧本、开始渲染”三个接口，同时保留一键成片。
3. 新增 `generation_tasks` 和 `generation_task_steps`。
4. Celery 任务每一步写入进度、错误和耗时。
5. 前端用 task_id 展示步骤级进度。
6. 分镜失败时展示具体错误，并支持重试失败分镜。
7. 成片支持预览和 9:16 导出。

### 第二阶段：把编辑能力做出来

目标：用户可以控制分镜，而不是只能接受一次性生成结果。

建议任务：

 1. 新增 script version 或至少保存 prompt_snapshot 和 script_content。
2. 分镜卡片支持编辑文案、字幕、画面 Prompt、时长。
3. 编辑后标记 dirty，不立即重跑整片。
4. 支持单分镜重生成图片、视频、配音。
5. 最终合成只在用户确认后触发。
6. 前端增加分镜时间轴和状态标记。

### 第三阶段：补答辩亮点

目标：让你的模块体现工程完整度和商业价值。

建议任务：

1. 增加 A/B 出片入口：同一个项目生成 2 到 3 个不同 Hook 版本。
2. 增加生成 trace 页面：展示 Prompt、模型、耗时、失败重试。
3. 增加导出多画幅：9:16、16:9、1:1。
4. 增加合规检查：敏感词、夸张承诺、来源声明。
5. 增加 Mock 数据看板：展示视频版本、Hook、风格、模拟点击率/转化率。

## 14. 最小改动版任务清单

如果时间很紧，建议优先做这 8 件事：

1. 修复你负责模块里的中文乱码和前端文案。
2. `create_project` 返回 `project_id` 后，不再强依赖同步完成所有生成步骤。
3. 新增任务表，至少记录 `task_id/status/progress/current_step/error_message`。
4. Celery 每个大步骤更新一次进度。
5. 前端增加任务进度面板，显示当前步骤和失败原因。
6. 分镜卡片增加“重生成该分镜”按钮。
7. 导出增加 9:16 和 16:9 参数。
8. README 或答辩文档里明确写出：RAG 检索由搭档负责，你的模块通过接口消费检索结果，并提供降级出片能力。

这样你的负责范围会非常清晰：你负责把用户从登录、建项目、生成、编辑、导出这一条主链路做稳定；RAG 则作为增强质量的能力接入，而不是你这边的核心实现负担。
