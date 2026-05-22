# 剧本生成模块开发规格说明书

## 1. 概述

剧本生成模块是 AIGC 带货视频生成系统的**创意引擎**，负责根据商品信息自动生成高质量的带货视频剧本。模块参考"找参考 → 提炼方法论 → 生产剧本"三步链路，沉淀优质视频库、模板、剧本三类核心实体。

### 1.1 所属链路位置

```
商品信息 + 素材 ──→ [剧本生成] ──→ 视频创作
   (输入)          本模块范围      (下游消费)
```

### 1.2 核心能力

- **爆款仿写**：参考爆款视频结构，融合商品信息生成同款剧本
- **灵感模板**：基于创作模板快速生成剧本
- **剧本自动化**：分层解耦策略库、因子库、约束库，动态组合生成
- **剧本干预**：支持用户对生成剧本进行微调和重生成

### 1.3 涉及的外部依赖

| 依赖 | 用途 |
|---|---|
| OpenAI/Anthropic API | LLM 生成剧本 |
| MySQL | 存储项目、剧本、模板记录 |
| ChromaDB | 向量检索（RAG） |
| 火山引擎 OpenAPI | 可选：调用特定模型 |

---

## 2. 功能分级

### P0 必做

- 基础剧本生成（输入商品信息 → 输出结构化剧本）
- 剧本存储与查询
- 剧本重新生成

### P1 进阶

- 爆款仿写模式
- 灵感模板模式
- 剧本干预（Prompt微调、分镜增删、台词改写）
- RAG 知识增强

### P2 加分项

- 优质视频库建设
- 方法论自动提炼
- 多剧本风格生成
- 因子库动态组合

---

## 3. 数据库表结构

### 3.1 scripts 表（已有）

```sql
CREATE TABLE scripts (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT NOT NULL COMMENT '所属项目',
    title            VARCHAR(200) COMMENT '剧本标题',
    content          TEXT NOT NULL COMMENT '剧本内容（JSON结构）',
    target_duration  INT COMMENT '目标时长(秒)',
    ai_model         VARCHAR(50) COMMENT '使用的AI模型',
    ai_prompt        TEXT COMMENT '生成使用的完整Prompt',
    generation_mode  VARCHAR(20) DEFAULT 'basic' COMMENT '生成模式：basic/template/imitate/auto',
    template_id      BIGINT COMMENT '关联的模板ID（template模式）',
    reference_id     BIGINT COMMENT '参考视频ID（imitate模式）',
    version          INT DEFAULT 1 COMMENT '版本号',
    parent_id        BIGINT COMMENT '父剧本ID（用于追踪修改历史）',
    status           VARCHAR(20) DEFAULT 'draft' COMMENT '状态：draft/approved/rejected',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    INDEX idx_project (project_id),
    INDEX idx_mode (generation_mode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='剧本表';
```

### 3.2 script_templates 表（新增）

```sql
CREATE TABLE script_templates (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    name             VARCHAR(200) NOT NULL COMMENT '模板名称',
    category         VARCHAR(50) COMMENT '类目：美妆/数码/食品/服饰等',
    strategy         TEXT COMMENT '策略描述',
    factors          JSON COMMENT '因子配置',
    constraints      JSON COMMENT '约束规则',
    example_scripts  JSON COMMENT '示例剧本ID列表',
    usage_count      INT DEFAULT 0 COMMENT '使用次数',
    effectiveness    FLOAT COMMENT '效果评分（基于转化数据）',
    status           VARCHAR(20) DEFAULT 'active' COMMENT '状态：active/deprecated',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_effectiveness (effectiveness)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='剧本模板表';
```

### 3.3 reference_videos 表（新增）

```sql
CREATE TABLE reference_videos (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    url              VARCHAR(500) COMMENT '原始视频URL',
    platform         VARCHAR(20) COMMENT '来源平台：tiktok/instagram/facebook',
    category         VARCHAR(50) COMMENT '类目',
    title            VARCHAR(200) COMMENT '视频标题',
    analysis_report  JSON COMMENT '结构化拆解报告',
    hook_type        VARCHAR(50) COMMENT 'Hook手法',
    selling_points   JSON COMMENT '卖点列表',
    style            VARCHAR(50) COMMENT '视觉风格',
    duration         INT COMMENT '时长(秒)',
    view_count       BIGINT COMMENT '播放量',
    like_count       BIGINT COMMENT '点赞数',
    status           VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform (platform),
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='参考视频库';
```

### 3.4 剧本 content JSON 结构

```json
{
    "opening": {
        "text": "开场白文本",
        "duration_sec": 3,
        "hook_type": "question/surprise/benefit",
        "tone": "excited/calm/urgent"
    },
    "body": [
        {
            "scene": 1,
            "text": "分镜台词",
            "duration_sec": 5,
            "visual_description": "画面描述",
            "image_keyword": "配图关键词",
            "camera_movement": "static/pan/zoom",
            "bgm_mood": "upbeat/soft/energetic",
            "subtitle_position": "bottom/top",
            "tts_audio_url": null,
            "image_url": null
        }
    ],
    "closing": {
        "text": "结尾话术",
        "duration_sec": 3,
        "cta_type": "purchase/follow/share",
        "urgency": "high/medium/low"
    },
    "full_text": "完整配音文本",
    "metadata": {
        "style": "professional/casual/funny",
        "target_audience": "年轻女性/科技爱好者",
        "product_category": "美妆/数码",
        "estimated_duration": 30
    }
}
```

---

## 4. API 接口定义

### 4.1 生成剧本（基础模式）

```
POST /api/v1/projects/{project_id}/scripts/generate
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| target_duration | int | 否 | 目标时长（秒），默认30 |
| voice_type | str | 否 | TTS音色 |
| style | str | 否 | 风格：professional/casual/funny |
| generation_mode | str | 否 | 生成模式：basic/template/imitate |
| template_id | int | 否 | 模板ID（template模式必填） |
| reference_id | int | 否 | 参考视频ID（imitate模式必填） |
| extra_instructions | str | 否 | 额外创作指令 |

**响应：**

```json
{
    "code": "0000000",
    "message": "剧本生成成功",
    "data": {
        "script_id": 1,
        "content": { "...剧本JSON..." },
        "generation_mode": "basic",
        "ai_model": "gpt-4o",
        "created_at": "2026-05-21T10:00:00"
    }
}
```

### 4.2 生成剧本（模板模式）

```
POST /api/v1/projects/{project_id}/scripts/generate-from-template
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| template_id | int | 是 | 模板ID |
| target_duration | int | 否 | 目标时长 |
| customizations | object | 否 | 自定义因子覆盖 |

### 4.3 生成剧本（仿写模式）

```
POST /api/v1/projects/{project_id}/scripts/imitate
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| reference_id | int | 是 | 参考视频ID |
| target_duration | int | 否 | 目标时长 |
| keep_structure | bool | 否 | 是否保持原结构，默认true |

### 4.4 干预剧本

```
POST /api/v1/scripts/{script_id}/intervene
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| intervention_type | str | 是 | 干预类型：prompt_adjust/scene_edit/dialogue_rewrite/factor_replace |
| scene_index | int | 否 | 干预的场景索引 |
| new_content | object | 否 | 新内容 |
| regenerate | bool | 否 | 是否重新生成，默认false |

**响应：**

```json
{
    "code": "0000000",
    "message": "剧本更新成功",
    "data": {
        "script_id": 2,
        "parent_id": 1,
        "version": 2,
        "content": { "...更新后的剧本JSON..." }
    }
}
```

### 4.5 查询剧本列表

```
GET /api/v1/projects/{project_id}/scripts
```

### 4.6 获取剧本详情

```
GET /api/v1/scripts/{script_id}
```

### 4.7 获取模板列表

```
GET /api/v1/script-templates
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| category | str | 否 | 按类目筛选 |
| min_effectiveness | float | 否 | 最低效果评分 |

### 4.8 获取参考视频库

```
GET /api/v1/reference-videos
```

---

## 5. Service 层接口定义

### 5.1 ScriptGenerationService

```python
class ScriptGenerationService:
    """剧本生成服务"""

    async def generate_script(
        self,
        db: AsyncSession,
        project_id: int,
        target_duration: int = 30,
        style: str = "professional",
        extra_instructions: str | None = None,
    ) -> Script:
        """
        基础模式生成剧本。

        流程：
        1. 读取项目商品信息
        2. RAG检索相关知识
        3. 构造Prompt
        4. 调用LLM生成
        5. 解析并保存
        """
        ...

    async def generate_from_template(
        self,
        db: AsyncSession,
        project_id: int,
        template_id: int,
        customizations: dict | None = None,
    ) -> Script:
        """
        模板模式生成剧本。

        流程：
        1. 读取模板配置
        2. 合并商品信息与模板因子
        3. 构造基于模板的Prompt
        4. 调用LLM生成
        """
        ...

    async def imitate_reference(
        self,
        db: AsyncSession,
        project_id: int,
        reference_id: int,
        keep_structure: bool = True,
    ) -> Script:
        """
        仿写模式生成剧本。

        流程：
        1. 读取参考视频分析报告
        2. 提取结构和风格特征
        3. 融合商品信息
        4. 生成同款剧本
        """
        ...

    async def intervene_script(
        self,
        db: AsyncSession,
        script_id: int,
        intervention_type: str,
        scene_index: int | None = None,
        new_content: dict | None = None,
        regenerate: bool = False,
    ) -> Script:
        """
        干预剧本。

        支持的干预类型：
        - prompt_adjust: 调整Prompt重新生成
        - scene_edit: 编辑单个分镜
        - dialogue_rewrite: 改写台词
        - factor_replace: 替换因子（如风格）
        """
        ...
```

### 5.2 PromptBuilder

```python
class PromptBuilder:
    """Prompt构造器"""

    def build_basic_prompt(
        self,
        product_info: dict,
        knowledge: list[str],
        target_duration: int,
        style: str,
    ) -> str:
        """构造基础模式Prompt"""
        ...

    def build_template_prompt(
        self,
        product_info: dict,
        template: ScriptTemplate,
        customizations: dict,
    ) -> str:
        """构造模板模式Prompt"""
        ...

    def build_imitate_prompt(
        self,
        product_info: dict,
        reference_analysis: dict,
    ) -> str:
        """构造仿写模式Prompt"""
        ...

    def build_intervention_prompt(
        self,
        original_script: dict,
        intervention_type: str,
        changes: dict,
    ) -> str:
        """构造干预重生成Prompt"""
        ...
```

### 5.3 VideoLibraryService (P2)

```python
class VideoLibraryService:
    """优质视频库服务"""

    async def analyze_reference_video(
        self,
        db: AsyncSession,
        video_url: str,
        platform: str,
    ) -> ReferenceVideo:
        """
        分析参考视频。

        生成结构化拆解报告：
        - Hook手法
        - 卖点提炼
        - 分镜结构
        - 视觉风格
        """
        ...

    async def extract_methodology(
        self,
        db: AsyncSession,
        video_ids: list[int],
    ) -> ScriptTemplate:
        """
        从一批视频提炼方法论。

        聚类分析，归纳为结构化创作模板。
        """
        ...
```

---

## 6. Prompt 模板设计

### 6.1 基础模式 Prompt

```
你是一个专业的电商带货视频编剧。根据以下商品信息，生成一个{target_duration}秒的带货短视频剧本。

【商品信息】
- 标题: {product_title}
- 卖点: {selling_points}
- 价格: {price}
- 目标人群: {target_audience}

【参考知识】
{knowledge_context}

【创作要求】
- 风格: {style}
- 开场3秒内必须有Hook吸引注意力
- 每个分镜5-8秒，节奏紧凑
- 结尾有明确的行动号召(CTA)
- 语言口语化，适合短视频配音

请严格按以下JSON格式输出：
{{
    "opening": {{
        "text": "开场白",
        "duration_sec": 3,
        "hook_type": "question/surprise/benefit"
    }},
    "body": [
        {{
            "scene": 1,
            "text": "分镜台词",
            "duration_sec": 5,
            "visual_description": "画面描述",
            "image_keyword": "配图关键词"
        }}
    ],
    "closing": {{
        "text": "结尾话术",
        "duration_sec": 3,
        "cta_type": "purchase"
    }},
    "full_text": "完整配音文本"
}}
```

### 6.2 模板模式 Prompt

```
你是一个专业的电商带货视频编剧。请基于以下创作模板，为商品生成带货剧本。

【创作模板】
名称: {template_name}
策略: {strategy}
因子配置:
{factors_json}

【商品信息】
{product_info}

【自定义调整】
{customizations}

请严格按照模板的策略和因子配置生成剧本，同时融合商品独特卖点。
```

### 6.3 仿写模式 Prompt

```
你是一个专业的电商带货视频编剧。请参考以下爆款视频的结构，为新商品生成同款剧本。

【参考视频分析】
Hook手法: {hook_type}
视频结构:
{structure_analysis}
视觉风格: {style}
卖点呈现方式: {selling_points_approach}

【新商品信息】
{product_info}

请保持参考视频的结构框架和风格，替换为新商品的内容。
```

---

## 7. 数据流图

```
┌────────────────────────────────────────────────────────────────────┐
│                       剧本生成模块数据流                             │
│                                                                    │
│  用户输入                                                           │
│     │                                                              │
│     ├─→ 基础模式                                                    │
│     │     │                                                        │
│     │     ▼                                                        │
│     │   ┌─────────────────────────────────────┐                    │
│     │   │ ① 读取项目信息 (MySQL)                │                    │
│     │   │ ② RAG检索知识 (ChromaDB + Embedding) │                    │
│     │   │ ③ 构造Prompt (PromptBuilder)         │                    │
│     │   │ ④ 调用LLM生成 (OpenAI/Anthropic)     │                    │
│     │   │ ⑤ 解析JSON输出                        │                    │
│     │   │ ⑥ 保存到scripts表                     │                    │
│     │   └─────────────────────────────────────┘                    │
│     │                                                              │
│     ├─→ 模板模式                                                    │
│     │     │                                                        │
│     │     ▼                                                        │
│     │   ┌─────────────────────────────────────┐                    │
│     │   │ ① 读取模板配置 (script_templates)     │                    │
│     │   │ ② 合并商品信息与因子                   │                    │
│     │   │ ③ 构造模板Prompt                      │                    │
│     │   │ ④ 调用LLM生成                         │                    │
│     │   │ ⑤ 保存剧本                            │                    │
│     │   └─────────────────────────────────────┘                    │
│     │                                                              │
│     └─→ 仿写模式                                                    │
│           │                                                        │
│           ▼                                                        │
│         ┌─────────────────────────────────────┐                    │
│         │ ① 读取参考视频分析 (reference_videos)  │                    │
│         │ ② 提取结构特征                         │                    │
│         │ ③ 融合商品信息                         │                    │
│         │ ④ 调用LLM生成                         │                    │
│         │ ⑤ 保存剧本                            │                    │
│         └─────────────────────────────────────┘                    │
│                                                                    │
│  剧本干预                                                           │
│     │                                                              │
│     ▼                                                              │
│  ┌─────────────────────────────────────┐                          │
│  │ ① 读取原剧本                         │                          │
│  │ ② 应用干预变更                       │                          │
│  │ ③ 如需重生成 → 调用LLM               │                          │
│  │ ④ 保存新版本（保留历史）              │                          │
│  └─────────────────────────────────────┘                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. 状态流转

### 8.1 剧本状态

```
draft ──→ approved ──→ used_in_production
  │           │
  └──→ rejected
```

| 状态 | 含义 |
|---|---|
| draft | 草稿，可编辑 |
| approved | 已审核通过 |
| rejected | 已拒绝 |
| used_in_production | 已用于视频生成 |

### 8.2 版本管理

```
script_v1 (parent_id=null)
    │
    ├──→ script_v2 (parent_id=1, intervention_type=prompt_adjust)
    │
    └──→ script_v3 (parent_id=1, intervention_type=scene_edit)
```

---

## 9. 目录结构规划

```
backend/app/
├── api/v1/
│   └── scripts.py                 # 剧本 API 路由
├── models/
│   └── script.py                  # Script ORM 模型（已有）
│   └── script_template.py         # ScriptTemplate ORM 模型
│   └── reference_video.py         # ReferenceVideo ORM 模型
├── schemas/
│   └── script.py                  # 剧本请求/响应模型（已有）
│   └── script_template.py         # 模板请求/响应模型
├── services/
│   ├── script_generation.py       # 剧本生成服务（已有，需扩展）
│   ├── prompt_builder.py          # Prompt构造器
│   ├── template_service.py        # 模板管理服务
│   └── video_library_service.py   # 参考视频库服务
└── workers/
    └── script_tasks.py            # 剧本相关异步任务
```

---

## 10. 实现顺序

| 阶段 | 任务 | 产出 | 依赖 |
|---|---|---|---|
| **Phase 1** | 基础剧本生成（真实LLM调用） | P0核心功能 | LLM API |
| **Phase 2** | 剧本干预功能 | 用户可编辑 | Phase 1 |
| **Phase 3** | 模板管理 + 模板模式生成 | P1功能 | Phase 1 |
| **Phase 4** | 参考视频库 + 仿写模式 | P1功能 | Phase 1 |
| **Phase 5** | RAG知识增强 | 生成质量提升 | ChromaDB |
| **Phase 6** | 方法论提炼 + 因子库 | P2功能 | Phase 3/4 |

---

## 11. 注意事项

1. **LLM输出解析**：返回可能不是合法JSON，需做容错处理（正则提取 + 默认值兜底）
2. **Prompt注入防护**：对用户输入的extra_instructions做安全过滤
3. **版本管理**：每次干预生成新版本，保留历史记录
4. **并发控制**：同一项目同时只能有一个生成任务
5. **缓存策略**：相似商品的Prompt和检索结果可缓存
6. **降级策略**：LLM不可用时，返回预设模板剧本
