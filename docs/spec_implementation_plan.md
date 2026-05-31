# AIGC 带货视频生成系统 — 开发计划

## 项目现状总结

**已完成（骨架）**：FastAPI 框架、ORM 三表模型、MinIO/Celery/MySQL 基础设施、火山引擎 LLM Provider 层、4 个基础 API 端点

**核心问题**：剧本生成、TTS、图片生成、视频合成均为 Mock 实现，系统无法产出真实视频

---

## 开发计划（按依赖顺序排列）

### 阶段一：剧本生成真实化（P0，约 2-3 天）

> 目标：输入商品信息 → 输出真实 LLM 生成的结构化剧本

**步骤 1.1 — 接入真实 LLM 生成剧本**
- 改造 `services/script_generation.py`，将 Mock 替换为调用 `vidmuse/provider/volcano.py` 的 `chat()` 方法
- 实现 `build_generation_prompt()` 方法，按 spec 中的 Prompt 模板构造提示词
- 处理 LLM 输出的 JSON 解析容错（正则提取 + 默认值兜底）
- **产出**：`POST /projects/{id}/generate` 返回真实剧本

**步骤 1.2 — 完善剧本 Schema 和存储**
- 扩展 `scripts` 表：新增 `generation_mode`、`version`、`parent_id`、`status` 字段（需 Alembic 迁移）
- 扩展 `schemas/script.py`，支持 spec 中定义的 content JSON 结构（opening/body/closing/full_text）
- **产出**：剧本可持久化，支持版本管理

**步骤 1.3 — 剧本查询与重新生成**
- 扩展 `GET /projects/{id}` 响应中包含完整剧本内容
- 完善 `POST /projects/{id}/regenerate-script` 使用真实 LLM
- **产出**：前端可查看和重新生成剧本

---

### 阶段二：TTS 配音真实化（P0，约 1-2 天）

> 目标：剧本 full_text → 真实 MP3 音频文件

**步骤 2.1 — 接入火山引擎 TTS**
- 改造 `services/tts_service.py`，对接火山引擎 TTS API
- 实现 `generate_audio(text, voice_type, speed, pitch)` → `AudioResult(path, duration, sample_rate)`
- 实现降级策略：火山引擎失败 → Edge TTS（免费备选）
- **产出**：Celery Worker Step 1 可生成真实音频

**步骤 2.2 — 音频上传与素材入库**
- TTS 生成后上传 MinIO，路径 `tasks/{task_id}/audio.mp3`
- 写入 `materials` 表（type=3, script_id, duration）
- **产出**：配音音频可追溯、可复用

---

### 阶段三：视频合成真实化（P0，约 2-3 天）

> 目标：图片 + 音频 + 字幕 → 真实 MP4 视频

**步骤 3.1 — FFmpeg 封装**
- 新建 `services/ffmpeg_wrapper.py`，封装核心方法：
  - `add_audio_to_video()` — 音视频合并
  - `add_subtitles()` — 字幕叠加
  - `convert_format()` — 格式/分辨率转换
- 确保 Dockerfile 安装 FFmpeg
- **产出**：底层视频处理能力

**步骤 3.2 — 视频合成服务**
- 改造 `services/video_composer.py`，替换 Mock 为真实 FFmpeg 合成逻辑
- 实现 `compose_frames(frames, output_dir, target_duration)` 流程：
  - 按 Frame 对象逐帧调用 Seedance 生成视频片段
  - 复用已有 video_url 的帧（非 dirty 状态）
  - 拼接所有片段，总裁剪到目标时长
  - 输出 MP4
- **产出**：`POST /projects/{id}/video/generate` 可产出真实视频

**步骤 3.3 — 场景配图策略**
- 改造 `services/image_service.py`，实现三级策略：
  - 优先：素材库匹配（按 image_keyword 检索）
  - 其次：使用商品主图 `project.product_image`
  - 兜底：生成纯色/文字占位图
- **产出**：每个分镜有对应配图

---

### 阶段四：任务状态与进度追踪（P0，约 1 天）

> 目标：前端可实时查看视频生成进度

**步骤 4.1 — 新建 video_tasks 表**
- 创建 `models/video_task.py` 和 `models/video_composition.py` ORM 模型
- Alembic 迁移新增 `video_tasks` 和 `video_compositions` 表
- **产出**：任务状态持久化

**步骤 4.2 — 进度更新机制**
- 改造 `workers/video_tasks.py`，每个步骤通过 `self.update_state(state='PROGRESS', meta={...})` 更新进度
- 同步更新 `video_tasks` 表的 `current_step` 和 `progress` 字段
- **产出**：Celery Task Meta 可查询实时进度

**步骤 4.3 — 进度查询 API**
- 新增 `GET /video-tasks/{task_id}/progress` 返回各步骤状态和百分比
- 新增 `GET /projects/{id}/video-tasks` 返回项目任务列表
- **产出**：前端可轮询进度

---

### 阶段五：素材管理模块（P1，约 2 天）

> 目标：独立的素材上传、管理、检索能力

**步骤 5.1 — 素材上传 API**
- 新建 `api/v1/materials.py`，实现：
  - `POST /materials/upload` — 单文件上传（multipart/form-data）
  - `POST /materials/batch-upload` — 批量上传
- 新建 `schemas/material.py` 定义请求/响应模型
- 实现 `services/material_service.py`：校验 → MinIO 上传 → MySQL 记录
- **产出**：素材可上传入库

**步骤 5.2 — 素材 CRUD API**
- `GET /materials` — 列表查询（分页、按 project_id/type/keyword 筛选）
- `GET /materials/{id}` — 详情
- `PUT /materials/{id}` — 更新标题/标签
- `DELETE /materials/{id}` — 删除（清理 MinIO + MySQL）
- **产出**：素材完整管理能力

---

### 阶段六：ChromaDB 向量检索（P1，约 1-2 天）

> 目标：RAG 知识检索 + 素材语义检索

**步骤 6.1 — ChromaDB 客户端初始化**
- 新建 `core/chromadb_client.py`，初始化 ChromaDB 连接和集合
- **产出**：向量库可用

**步骤 6.2 — Embedding 生成与入库**
- 新建 `services/material_analysis.py`，实现：
  - `generate_embedding()` — 调用火山引擎 Embedding 模型
  - `extract_features()` — 调用多模态 LLM 提取图片特征
  - `generate_tags()` — 生成三层标签
- 上传素材时触发异步分析任务
- **产出**：素材自动结构化

**步骤 6.3 — 语义检索服务**
- 新建 `services/material_search.py`
- 实现 `POST /materials/search` 接口（keyword/semantic 两种模式）
- 剧本生成时接入 RAG 检索
- **产出**：素材语义检索 + 剧本生成质量提升

---

### 阶段七：剧本进阶功能（P1，约 2-3 天）

**步骤 7.1 — 剧本干预**
- 实现 `POST /scripts/{id}/intervene` 接口
- 支持四种干预类型：prompt_adjust / scene_edit / dialogue_rewrite / factor_replace
- 每次干预生成新版本（parent_id 关联）
- **产出**：用户可微调剧本

**步骤 7.2 — 模板模式**
- 新增 `script_templates` 表和 ORM 模型
- 实现模板 CRUD API
- 实现 `POST /projects/{id}/scripts/generate-from-template`
- **产出**：基于模板快速生成剧本

**步骤 7.3 — 仿写模式**
- 新增 `reference_videos` 表和 ORM 模型
- 实现参考视频库 API
- 实现 `POST /projects/{id}/scripts/imitate`
- **产出**：爆款仿写能力

---

### 阶段八：视频进阶功能（P2，约 2-3 天）

**步骤 8.1 — 分镜级干预**
- 实现 `POST /video-tasks/{id}/scenes/{index}/intervene`
- 支持 5 种操作：replace_image / replace_audio / edit_subtitle / change_duration / regenerate
- 仅重渲染受影响的分镜后拼接
- **产出**：精细编辑能力

**步骤 8.2 — 多格式导出**
- 实现 `POST /video-tasks/{id}/export`
- 支持 9:16 / 16:9 / 1:1 画幅
- 支持 high/medium/low 质量
- **产出**：适配多平台

**步骤 8.3 — AI 智能配图**
- 对接火山引擎文生图 API
- 按 image_keyword 生成场景配图
- **产出**：配图从占位升级为 AI 生成

---

## 推荐执行顺序

```
阶段一（剧本真实化）
  ↓
阶段二（TTS 真实化）  ← 可与阶段一并行
  ↓
阶段三（视频合成真实化）  ← 依赖阶段二
  ↓
阶段四（任务状态追踪）  ← 可与阶段三并行
  ↓
---- P0 完成，系统可端到端跑通 ----
  ↓
阶段五（素材管理）  ← 独立，随时可做
  ↓
阶段六（ChromaDB）  ← 依赖阶段五
  ↓
阶段七（剧本进阶）  ← 依赖阶段一
  ↓
阶段八（视频进阶）  ← 依赖阶段三
```

**P0 总预估**：约 7-10 天，完成后系统可从商品信息到视频产出全链路跑通。
