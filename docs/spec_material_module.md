# 素材模块开发规格说明书

## 1. 概述

素材模块是 AIGC 带货视频生成系统的**基础能力层**，负责管理视频生成所需的各类素材资产，包括商品图片、视频片段、背景音乐、配音音频等。模块提供素材的上传、结构化处理、多模态理解、检索召回等核心能力。

### 1.1 所属链路位置

```
用户上传素材 ──→ [素材入库] ──→ [结构化处理] ──→ [检索召回] ──→ 剧本/创作模块消费
   (前端)         本模块范围        本模块范围        本模块范围      (下游消费)
```

### 1.2 核心价值

- **资产沉淀**：将商家上传的素材转化为可被 AI 消费的结构化资产
- **智能召回**：支持多维度检索，为剧本生成和视频创作提供精准素材匹配
- **质量保障**：通过多模态理解提取素材特征，确保生成视频的质量

### 1.3 涉及的外部依赖

| 依赖 | 用途 |
|---|---|
| MinIO | 素材文件存储（图片/视频/音频） |
| MySQL | 素材元数据存储 |
| ChromaDB | 素材 Embedding 向量存储与检索 |
| 火山引擎 OpenAPI | 文生图、图生视频等模型调用 |
| OpenAI/其他 LLM | 多模态理解（图片描述、标签提取） |

---

## 2. 功能分级

### P0 必做

- 素材上传（图片/视频/音频）
- 基础元数据管理（类型、标题、标签）
- 素材列表查询与详情查看
- 素材删除与更新

### P1 进阶

- 素材自动标签（AI 提取）
- Embedding 向量化存储
- 基于关键词/标签的检索
- 基于向量相似度的语义检索

### P2 加分项

- 多模态理解（图片内容描述、视频摘要）
- 素材切片（视频按场景切分为 slice）
- 三层标签体系（商品/视频/slice 维度）
- 素材质量评分

---

## 3. 数据库表结构

### 3.1 materials 表（已有）

```sql
CREATE TABLE materials (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id       BIGINT COMMENT '所属项目（NULL表示通用素材）',
    script_id        BIGINT COMMENT '关联的剧本',
    type             TINYINT NOT NULL COMMENT '素材类型：1=商品图 2=背景音乐 3=配音音频 4=字幕 5=成品视频 6=视频片段 7=参考素材',
    title            VARCHAR(200) COMMENT '素材标题',
    url              VARCHAR(500) NOT NULL COMMENT '存储URL（MinIO路径）',
    file_size        BIGINT COMMENT '文件大小(字节)',
    duration         INT COMMENT '时长(秒)，音视频素材',
    format           VARCHAR(20) COMMENT '文件格式：mp4/mp3/wav/png/jpg',
    ai_features      JSON COMMENT 'AI特征（见下文结构）',
    source_type      TINYINT DEFAULT 0 COMMENT '来源：0=用户上传 1=AI生成 2=系统模板',
    scene_index      INT COMMENT '所属场景序号（对应剧本body.scene）',
    tags             JSON COMMENT '标签列表',
    embedding_id     VARCHAR(100) COMMENT 'ChromaDB中的向量ID',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_type (type),
    INDEX idx_source (source_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='素材表';
```

### 3.2 ai_features 字段结构

```json
{
    "description": "AI生成的素材描述",
    "objects": ["商品", "人物", "场景"],
    "style": "简约/时尚/复古",
    "colors": ["#FF0000", "#00FF00"],
    "quality_score": 0.85,
    "resolution": "1920x1080",
    "aspect_ratio": "16:9",
    "has_text": false,
    "dominant_color": "#FFFFFF",
    "scene_type": "product_show/lifestyle/tutorial"
}
```

### 3.3 tags 字段结构

```json
{
    "product": ["手机", "数码", "科技"],
    "scene": ["办公", "户外", "家庭"],
    "style": ["简约", "商务", "时尚"],
    "mood": ["专业", "活力", "温馨"]
}
```

---

## 4. API 接口定义

### 4.1 上传素材

```
POST /api/v1/materials/upload
```

**请求参数（multipart/form-data）：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | File | 是 | 素材文件 |
| project_id | int | 否 | 所属项目ID（不传则为通用素材） |
| type | int | 是 | 素材类型：1=商品图 2=背景音乐 3=配音音频 6=视频片段 7=参考素材 |
| title | str | 否 | 素材标题（默认使用文件名） |
| tags | str | 否 | 标签（JSON 数组字符串） |

**响应：**

```json
{
    "code": "0000000",
    "message": "上传成功",
    "data": {
        "id": 1,
        "title": "商品主图.jpg",
        "url": "http://minio:9000/aigc-materials/materials/1/abc123.jpg",
        "type": 1,
        "file_size": 1024000,
        "format": "jpg",
        "tags": ["商品", "手机"],
        "created_at": "2026-05-21T10:00:00"
    }
}
```

### 4.2 批量上传素材

```
POST /api/v1/materials/batch-upload
```

**请求参数（multipart/form-data）：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| files | File[] | 是 | 多个素材文件 |
| project_id | int | 否 | 所属项目ID |
| type | int | 是 | 素材类型 |

**响应：**

```json
{
    "code": "0000000",
    "message": "批量上传成功",
    "data": {
        "total": 5,
        "success": 5,
        "failed": 0,
        "materials": [
            { "id": 1, "title": "image1.jpg", "status": "success" },
            { "id": 2, "title": "image2.jpg", "status": "success" }
        ]
    }
}
```

### 4.3 查询素材列表

```
GET /api/v1/materials
```

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| project_id | int | 否 | 按项目筛选 |
| type | int | 否 | 按类型筛选 |
| keyword | str | 否 | 关键词搜索（标题/标签） |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

**响应：**

```json
{
    "code": "0000000",
    "message": "操作成功",
    "data": {
        "total": 100,
        "page": 1,
        "page_size": 20,
        "items": [
            {
                "id": 1,
                "title": "商品主图",
                "type": 1,
                "url": "http://...",
                "tags": ["商品", "手机"],
                "ai_features": { "...": "..." },
                "created_at": "2026-05-21T10:00:00"
            }
        ]
    }
}
```

### 4.4 获取素材详情

```
GET /api/v1/materials/{material_id}
```

**响应：**

```json
{
    "code": "0000000",
    "message": "操作成功",
    "data": {
        "id": 1,
        "project_id": 1,
        "title": "商品主图",
        "type": 1,
        "url": "http://...",
        "file_size": 1024000,
        "duration": null,
        "format": "jpg",
        "source_type": 0,
        "tags": ["商品", "手机", "科技"],
        "ai_features": {
            "description": "一部黑色智能手机，放置在白色桌面上",
            "objects": ["手机", "桌子"],
            "style": "简约",
            "quality_score": 0.92
        },
        "created_at": "2026-05-21T10:00:00"
    }
}
```

### 4.5 更新素材信息

```
PUT /api/v1/materials/{material_id}
```

**请求参数（JSON）：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | str | 否 | 更新标题 |
| tags | list[str] | 否 | 更新标签 |
| project_id | int | 否 | 更新所属项目 |

### 4.6 删除素材

```
DELETE /api/v1/materials/{material_id}
```

### 4.7 素材检索（P1）

```
POST /api/v1/materials/search
```

**请求参数（JSON）：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | str | 是 | 搜索查询文本 |
| project_id | int | 否 | 限定项目范围 |
| type | int | 否 | 限定素材类型 |
| search_type | str | 否 | 检索类型：keyword（默认）/ semantic（语义） |
| top_k | int | 否 | 返回数量，默认 10 |

**响应：**

```json
{
    "code": "0000000",
    "message": "操作成功",
    "data": {
        "total": 5,
        "items": [
            {
                "id": 1,
                "title": "商品主图",
                "url": "http://...",
                "score": 0.95,
                "match_reason": "标题匹配 + 标签匹配"
            }
        ]
    }
}
```

---

## 5. Service 层接口定义

### 5.1 MaterialService

```python
class MaterialService:
    """素材管理服务"""

    async def upload_material(
        self,
        db: AsyncSession,
        file: UploadFile,
        project_id: int | None,
        material_type: int,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> Material:
        """
        上传素材。

        流程：
        1. 校验文件类型和大小
        2. 上传文件到 MinIO
        3. 创建素材记录到 MySQL
        4. 触发异步任务：AI 特征提取 + Embedding
        """
        ...

    async def batch_upload(
        self,
        db: AsyncSession,
        files: list[UploadFile],
        project_id: int | None,
        material_type: int,
    ) -> BatchUploadResult:
        """批量上传素材"""
        ...

    async def get_material_list(
        self,
        db: AsyncSession,
        project_id: int | None = None,
        material_type: int | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MaterialListResult:
        """查询素材列表"""
        ...

    async def get_material_detail(
        self,
        db: AsyncSession,
        material_id: int,
    ) -> Material:
        """获取素材详情"""
        ...

    async def update_material(
        self,
        db: AsyncSession,
        material_id: int,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> Material:
        """更新素材信息"""
        ...

    async def delete_material(
        self,
        db: AsyncSession,
        material_id: int,
    ) -> None:
        """
        删除素材。

        流程：
        1. 删除 MinIO 中的文件
        2. 删除 ChromaDB 中的 Embedding
        3. 删除 MySQL 记录
        """
        ...
```

### 5.2 MaterialAnalysisService

```python
class MaterialAnalysisService:
    """素材分析服务（AI 能力）"""

    async def extract_features(
        self,
        material_id: int,
        file_path: str,
        material_type: int,
    ) -> dict:
        """
        提取素材 AI 特征。

        根据素材类型调用不同的分析能力：
        - 图片：内容描述、物体识别、风格分析、颜色提取
        - 视频：场景识别、关键帧提取、内容摘要
        - 音频：语音识别、情感分析
        """
        ...

    async def generate_tags(
        self,
        material_id: int,
        features: dict,
    ) -> list[str]:
        """
        基于 AI 特征生成标签。

        三层标签体系：
        - 商品维度：品类、品牌、属性
        - 视频维度：风格、场景、情绪
        - 切片维度：具体内容描述
        """
        ...

    async def generate_embedding(
        self,
        material_id: int,
        content: str,
    ) -> str:
        """
        生成素材 Embedding 向量。

        存储到 ChromaDB，返回向量 ID。
        """
        ...

    async def search_similar(
        self,
        query: str,
        project_id: int | None = None,
        material_type: int | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """
        语义检索相似素材。

        基于 ChromaDB 向量检索。
        """
        ...
```

### 5.3 MaterialSliceService (P2)

```python
class MaterialSliceService:
    """素材切片服务"""

    async def slice_video(
        self,
        material_id: int,
        video_path: str,
    ) -> list[MaterialSlice]:
        """
        视频切片。

        将长视频按场景切分为多个短片段（slice），
        每个 slice 有独立的标签和特征。
        """
        ...

    async def analyze_slice(
        self,
        slice_id: int,
    ) -> dict:
        """
        分析单个切片。

        提取切片级别的细粒度特征：
        - 画面内容
        - 镜头运动
        - 人物动作
        - 产品展示角度
        """
        ...
```

---

## 6. 数据流图

```
┌────────────────────────────────────────────────────────────────────┐
│                         素材模块完整数据流                           │
│                                                                    │
│  POST /api/v1/materials/upload                                     │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────────────────────────┐                       │
│  │          MaterialService                │                       │
│  │                                         │                       │
│  │  ① 校验文件类型/大小                      │                       │
│  │  ② 上传文件到 MinIO                       │                       │
│  │  ③ 创建素材记录到 MySQL                   │                       │
│  │  ④ 发送异步任务到 Celery                   │                       │
│  └────────────────┬────────────────────────┘                       │
│                   │                                                │
│                   ▼                                                │
│  ┌─────────────────────────────────────────┐                       │
│  │       MaterialAnalysisService           │                       │
│  │       (Celery Worker 异步执行)           │                       │
│  │                                         │                       │
│  │  ⑤ 多模态理解：提取 AI 特征               │                       │
│  │     - 图片：物体/风格/颜色                │                       │
│  │     - 视频：场景/关键帧                   │                       │
│  │     - 音频：语音/情感                     │                       │
│  │                                         │                       │
│  │  ⑥ 标签生成：三层标签体系                 │                       │
│  │     - 商品维度                           │                       │
│  │     - 视频维度                           │                       │
│  │     - 切片维度                           │                       │
│  │                                         │                       │
│  │  ⑦ Embedding 生成：向量化存储             │                       │
│  │     - 生成文本描述                       │                       │
│  │     - 调用 Embedding 模型                │                       │
│  │     - 存储到 ChromaDB                    │                       │
│  │                                         │                       │
│  │  ⑧ 回写 MySQL：更新 ai_features/tags     │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                    │
│  GET /api/v1/materials/search                                      │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────────────────────────────┐                       │
│  │          检索召回                         │                       │
│  │                                         │                       │
│  │  keyword 检索：                          │                       │
│  │    - 标题 LIKE 匹配                      │                       │
│  │    - tags JSON 查询                      │                       │
│  │                                         │                       │
│  │  semantic 检索：                         │                       │
│  │    - 文本 Embedding                      │                       │
│  │    - ChromaDB 向量检索                   │                       │
│  │    - 相似度排序                          │                       │
│  │                                         │                       │
│  │  混合检索：                              │                       │
│  │    - keyword 权重 + semantic 权重         │                       │
│  │    - 综合评分排序                        │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                    │
│  下游消费：                                                         │
│    - 剧本生成：根据商品描述检索相关素材参考                           │
│    - 视频创作：根据分镜脚本检索匹配素材切片                           │
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. 状态流转

### 7.1 素材生命周期

```
上传中 ──→ 处理中 ──→ 可用
              │         │
              └──→ 失败  └──→ 已删除
```

| 状态 | 含义 |
|---|---|
| uploading | 文件正在上传到 MinIO |
| processing | AI 正在分析处理 |
| available | 可用，已入库 |
| failed | 处理失败（记录失败原因） |
| deleted | 已删除（软删除） |

### 7.2 素材类型枚举

| 类型值 | 含义 | 支持格式 | 最大大小 |
|---|---|---|---|
| 1 | 商品图 | jpg, png, webp | 10MB |
| 2 | 背景音乐 | mp3, wav | 50MB |
| 3 | 配音音频 | mp3, wav | 50MB |
| 4 | 字幕 | srt, ass | 1MB |
| 5 | 成品视频 | mp4 | 500MB |
| 6 | 视频片段 | mp4 | 100MB |
| 7 | 参考素材 | jpg, png, mp4 | 100MB |

---

## 8. 异常处理

### 8.1 错误码

| 错误码 | 含义 |
|---|---|
| M010001 | 文件格式不支持 |
| M010002 | 文件大小超限 |
| M010003 | 文件上传失败 |
| M010004 | 素材不存在 |
| M010005 | 素材处理失败 |
| M010006 | Embedding 生成失败 |
| M010007 | 检索服务异常 |

### 8.2 失败重试策略

- **文件上传失败**：自动重试 3 次，间隔 1s/2s/4s
- **AI 分析失败**：自动重试 2 次，记录失败原因
- **Embedding 生成失败**：降级为关键词检索

---

## 9. 目录结构规划

```
backend/app/
├── api/v1/
│   └── materials.py              # 素材 API 路由
├── models/
│   └── material.py               # Material ORM 模型（已有）
├── schemas/
│   └── material.py               # 素材请求/响应 Pydantic 模型
├── services/
│   ├── material_service.py       # 素材管理服务
│   ├── material_analysis.py      # 素材分析服务（AI）
│   └── material_search.py        # 素材检索服务
├── workers/
│   └── material_tasks.py         # 素材处理异步任务
└── core/
    └── chromadb_client.py        # ChromaDB 客户端初始化
```

---

## 10. 实现顺序

| 阶段 | 任务 | 产出 | 依赖 |
|---|---|---|---|
| **Phase 1** | 素材上传 + MinIO 存储 + 基础 CRUD | P0 核心功能 | MinIO |
| **Phase 2** | 素材列表/详情 API + 前端页面 | 可用的素材管理 | Phase 1 |
| **Phase 3** | AI 特征提取 + 标签生成 | 素材结构化 | LLM API |
| **Phase 4** | Embedding 生成 + 语义检索 | 智能召回能力 | ChromaDB |
| **Phase 5** | 视频切片 + Slice 分析 | 细粒度素材管理 | Phase 3 |

---

## 11. 注意事项

1. **文件大小限制**：根据素材类型设置不同的大小限制，超限返回明确错误
2. **格式校验**：严格校验文件格式，防止恶意文件上传
3. **存储路径规范**：MinIO 路径按 `materials/{material_id}/{filename}` 组织
4. **异步处理**：AI 分析和 Embedding 生成必须异步执行，避免阻塞上传接口
5. **降级策略**：Embedding 服务不可用时，降级为关键词检索
6. **清理机制**：删除素材时，同步清理 MinIO 文件和 ChromaDB 向量
7. **并发控制**：批量上传时限制并发数，避免压垮 AI 分析服务
