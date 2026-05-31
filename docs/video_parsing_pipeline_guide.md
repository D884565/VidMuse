# 视频解析流水线设计文档
## 一、整体架构
视频解析流水线采用**责任链模式**设计，将复杂的视频解析流程拆分为多个独立的处理器，每个处理器负责单一职责，通过上下文传递数据，实现高内聚低耦合的架构。
### 完整处理流程
```
┌─────────────────────────────────────────────────────────────────┐
│                      初始输入数据                               │
│  video_id: str            视频唯一ID                           │
│  object_name: str         视频在对象存储中的路径                │
│  video_duration: int      视频总时长（毫秒）                    │
│  meta_data: Dict          可选，自定义元数据                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. VideoSplitProcessor    视频拆分处理器                        │
│  - 将完整视频拆分为多个5秒（可配置）的短视频分片                 │
│  - 为每个分片提取封面图                                       │
│  - 上传分片和封面图到对象存储                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. VideoUnderstandingProcessor  分片理解处理器                  │
│  - 调用多模态大模型分析每个视频分片的内容                       │
│  - 输出结构化的分片理解结果（模板类型、创作要素、生成Prompt等）  │
│  - 生成扁平化的分片数据，用于向量化                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SliceGenerateProcessor  分片JSON生成处理器                   │
│  - 根据理解结果生成符合模板要求的分片JSON文件                   │
│  - 输出结构化的分片数据列表，供后续校验使用                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SchemaValidationProcessor  分片结构校验处理器                │
│  - 使用JSON Schema校验分片数据是否符合规范要求                 │
│  - 分离有效分片和无效分片，输出校验汇总信息                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. VectorizationProcessor  分片向量化处理器（可选）             │
│  - 将分片文本和封面图转换为向量                                 │
│  - 存储到向量数据库，用于后续检索                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. VideoAggregationProcessor  分片聚合处理器                    │
│  - 聚合所有有效分片的理解结果                                   │
│  - 生成分片索引列表、全量台词等聚合数据，供整体理解使用         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. VideoOverallUnderstandingProcessor  视频整体理解处理器        │
│  - 基于所有分片的聚合结果，分析整个视频的整体信息               │
│  - 输出结构化的视频整体理解结果（商品信息、目标人群、节奏分析等）│
│  - 生成扁平化的整体视频数据，用于向量化                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. VideoGenerateProcessor  视频整体JSON生成处理器               │
│  - 根据整体理解结果生成符合模板要求的完整视频JSON文件           │
│  - 输出结构化的视频整体数据，供后续校验使用                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. SchemaValidationProcessor  整体结构校验处理器                │
│  - 使用JSON Schema校验视频整体数据是否符合规范要求             │
│  - 输出校验结果和汇总信息                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. VectorizationProcessor  整体向量化处理器（可选）            │
│  - 将视频整体数据转换为向量                                     │
│  - 存储到向量数据库，用于后续检索                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      最终输出结果                               │
│  success: bool           处理是否成功                           │
│  data: Dict              所有中间和最终数据                     │
│  errors: List[str]       错误信息列表                           │
│  metadata: Dict          处理元数据（耗时、计数等）             │
└─────────────────────────────────────────────────────────────────┘
```
---
## 二、上下文数据传递约定
所有处理器通过`PipelineContext`对象传递数据，严格遵守以下约定：
### 1. 数据命名规则
- 键名使用小写蛇形命名法，如`video_id`、`slices_url`
- 输出数据键名尽量体现业务含义，避免歧义
- 临时数据可存入`context.metadata`，不进入最终结果
### 2. 全局通用字段（初始输入）
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `video_id` | str | 是 | 视频唯一ID |
| `object_name` | str | 是 | 视频在对象存储中的路径 |
| `video_duration` | int | 是 | 视频总时长，单位毫秒 |
| `meta_data` | Dict | 否 | 自定义元数据，会自动合并到向量元数据中 |
### 3. 各处理器输入输出详情
---
#### 📌 处理器1：VideoSplitProcessor（视频拆分处理器）
**功能**：将完整视频拆分为多个短视频分片，提取封面图
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `video_id` | str | 初始输入 | 视频唯一ID |
| `object_name` | str | 初始输入 | 视频在对象存储中的路径 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `count` | int | 分片总数量 |
| `slices_url` | List[str] | 分片视频的公网URL列表 |
| `images_url` | List[str] | 分片封面图的公网URL列表 |
| `slices_object_name` | List[str] | 分片视频在对象存储中的路径列表 |
| `images_object_name` | List[str] | 分片封面图在对象存储中的路径列表 |
---
#### 📌 处理器2：VideoUnderstandingProcessor（分片理解处理器）
**功能**：调用大模型分析每个视频分片的内容，输出结构化结果
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `slices_url` | List[str] | VideoSplitProcessor | 分片视频URL列表 |
| `images_url` | List[str] | VideoSplitProcessor | 分片封面图URL列表 |
| `slices_object_name` | List[str] | VideoSplitProcessor | 分片对象存储路径列表 |
| `images_object_name` | List[str] | VideoSplitProcessor | 封面图对象存储路径列表 |
| `count` | int | VideoSplitProcessor | 分片总数量 |
| `video_id` | str | 初始输入 | 视频唯一ID |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `understood_slices` | List[Dict] | 理解后的完整分片数据，包含基础信息和理解结果 |
| `embed_slices` | List[str] | 扁平化后的分片数据JSON字符串，用于向量化 |
| `slice_cover_urls` | List[str] | 分片封面图URL列表，用于图像向量化 |
**`understood_slices`结构示例：**
```python
{
    "slice_id": "v_001_slice_0",
    "video_id": "v_001",
    "slice_index": 0,
    "slice_url": "https://example.com/slice_0.mp4",
    "cover_url": "https://example.com/cover_0.jpg",
    "slice_object_name": "video/v_001_slice_0.mp4",
    "cover_object_name": "video/v_001_slice_0.jpg",
    "understanding": {
        "模板名称": "主播情绪开场",
        "模板类型": "HOOK",
        "创作要素": {
            "画面": "主播穿着红色连衣裙出镜",
            "动作": "挥手打招呼",
            "台词": "姐妹们，今天给大家带来一款超好用的产品！",
            "运镜": "固定镜头",
            "时长": "3-5秒",
            "情绪评分": 0.9
        },
        "生成Prompt完整模板": "一位穿着红色连衣裙的女主播挥手打招呼，微笑着说：姐妹们，今天给大家带来一款超好用的产品！"
    }
}
```
---
#### 📌 处理器3：SliceGenerateProcessor（分片JSON生成处理器）
**功能**：生成符合模板要求的分片JSON文件
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `understood_slices` | List[Dict] | VideoUnderstandingProcessor | 理解后的分片数据 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `slice_files` | List[str] | 生成的分片JSON文件路径列表 |
| `slice_data` | List[Dict] | 结构化的分片数据列表，符合Schema要求 |
---
#### 📌 处理器4：SchemaValidationProcessor（分片结构校验处理器）
**功能**：校验分片数据是否符合JSON Schema规范
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `slice_data` | List[Dict] | SliceGenerateProcessor | 待校验的分片数据 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `valid_slices` | List[Dict] | 校验通过的分片数据列表 |
| `invalid_slices` | List[Dict] | 校验失败的分片数据列表，包含错误信息 |
| `slice_validation_summary` | Dict | 校验汇总信息：`total`、`valid`、`invalid` |
---
#### 📌 处理器5：VectorizationProcessor（分片向量化处理器）
**功能**：将分片文本和封面图转换为向量并存入向量数据库
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `embed_slices` | List[str] | VideoUnderstandingProcessor | 扁平化的分片文本数据 |
| `slice_cover_urls` | List[str] | VideoUnderstandingProcessor | 分片封面图URL列表 |
| `meta_data` | Dict | 初始输入 | 自定义元数据 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `vectorization_result` | Dict | 向量化结果：`count`、`ids`、`documents`、`metadatas` |
---
#### 📌 处理器6：VideoAggregationProcessor（分片聚合处理器）
**功能**：聚合所有分片信息，为整体理解做准备
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `understood_slices` | List[Dict] | VideoUnderstandingProcessor | 所有理解后的分片数据 |
| `valid_slices` | List[Dict] | SchemaValidationProcessor | 校验通过的分片数据（可选，优先使用） |
| `video_id` | str | 初始输入 | 视频唯一ID |
| `video_duration` | int | 初始输入 | 视频总时长 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `aggregated_video_data` | Dict | 聚合后的完整视频数据 |
| `segment_list` | List[Dict] | 分片索引列表，供整体理解使用 |
| `all_script_lines` | List[str] | 所有分片的台词列表 |
---
#### 📌 处理器7：VideoOverallUnderstandingProcessor（视频整体理解处理器）
**功能**：分析整个视频的整体信息，输出结构化结果
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `aggregated_video_data` | Dict | VideoAggregationProcessor | 聚合后的视频数据 |
| `segment_list` | List[Dict] | VideoAggregationProcessor | 分片索引列表 |
| `all_script_lines` | List[str] | VideoAggregationProcessor | 所有分片的台词列表 |
| `video_id` | str | 初始输入 | 视频唯一ID |
| `video_duration` | int | 初始输入 | 视频总时长 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ai_features` | Dict | 视频整体理解结构化结果 |
| `embed_video` | str | 扁平化的整体视频数据JSON字符串，用于向量化 |
**`ai_features`结构示例：**
```python
{
    "视频基本信息": {
        "video_id": "v_001",
        "商品名称": "粉色碎花连衣裙",
        "目标人群": "18-35岁女性",
        "总时长_ms": 30000,
        "原片核心文案": [
            "姐妹们，今天给大家带来一款超好用的产品！",
            "这款连衣裙采用雪纺面料，穿着非常舒适。",
            "现在下单只要159元，还赠送运费险哦！"
        ]
    },
    "片段间关系": {
        "转场序列": ["硬切", "硬切", "叠化", "硬切"],
        "情绪曲线": ["高涨→平稳", "平稳→微升", "微升→高涨", "高涨→平稳"],
        "视觉节奏": "整体节奏明快，镜头切换频率适中",
        "BGM节奏匹配": "BGM为轻快的流行音乐，与画面节奏高度匹配"
    }
}
```
---
#### 📌 处理器8：VideoGenerateProcessor（视频整体JSON生成处理器）
**功能**：生成符合模板要求的完整视频JSON文件
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `ai_features` | Dict | VideoOverallUnderstandingProcessor | 视频整体理解结果 |
| `aggregated_video_data` | Dict | VideoAggregationProcessor | 聚合后的视频数据 |
| `video_id` | str | 初始输入 | 视频唯一ID |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `video_file` | str | 生成的完整视频JSON文件路径 |
| `video_data` | Dict | 结构化的视频整体数据，符合Schema要求 |
---
#### 📌 处理器9：SchemaValidationProcessor（整体结构校验处理器）
**功能**：校验视频整体数据是否符合JSON Schema规范
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `video_data` | List[Dict] | VideoGenerateProcessor | 待校验的视频整体数据 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `valid_video` | List[Dict] | 校验通过的视频数据列表 |
| `invalid_video` | List[Dict] | 校验失败的视频数据列表，包含错误信息 |
| `video_validation_summary` | Dict | 校验汇总信息：`total`、`valid`、`invalid` |
---
#### 📌 处理器10：VectorizationProcessor（整体向量化处理器）
**功能**：将视频整体数据转换为向量并存入向量数据库
**输入（从上下文获取）：**
| 字段名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `embed_video` | str | VideoOverallUnderstandingProcessor | 扁平化的整体视频数据 |
| `meta_data` | Dict | 初始输入 | 自定义元数据 |
**输出（写入上下文）：**
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `vectorization_result` | Dict | 向量化结果：`count`、`ids`、`documents`、`metadatas` |
---
## 三、使用示例
### 1. 基础使用（默认完整流程）
```python
from backend.v1.app.pipeline.pipelines import VideoParsingPipeline
# 创建流水线，使用默认完整流程，启用向量化
pipeline = VideoParsingPipeline(enable_vectorization=True)
# 执行流水线
result = pipeline.run({
    "video_id": "v_001",
    "object_name": "video/test_video.mp4",
    "video_duration": 30000,  # 30秒
    "meta_data": {
        "source": "douyin",
        "category": "clothing"
    }
})
# 处理结果
if result["success"]:
    print("视频解析成功！")
    print(f"有效分片数量：{result['data']['slice_validation_summary']['valid']}")
    print(f"分片向量化数量：{result['data']['vectorization_result']['count']}")
    print(f"视频整体理解结果：{result['data']['ai_features']['视频基本信息']['商品名称']}")
else:
    print(f"视频解析失败：{result['errors']}")
```
### 2. 自定义处理器链
```python
from backend.v1.app.pipeline.pipelines import VideoParsingPipeline
from backend.v1.app.pipeline.processors import (
    VideoSplitProcessor,
    VideoUnderstandingProcessor,
    SchemaValidationProcessor
)
# 只需要视频拆分、理解、校验的简化流程
custom_processors = [
    VideoSplitProcessor(slice_duration=3000),  # 3秒一个分片
    VideoUnderstandingProcessor(),
    SchemaValidationProcessor.for_slice()
]
pipeline = VideoParsingPipeline(custom_processors=custom_processors)
result = pipeline.run({
    "video_id": "v_002",
    "object_name": "video/short_video.mp4",
    "video_duration": 15000
})
```
### 3. 自定义Schema路径
```python
pipeline = VideoParsingPipeline(
    slice_schema_path="/path/to/custom_slice_schema.json",
    video_schema_path="/path/to/custom_video_schema.json"
)
```
---
## 四、扩展开发指南
### 新增自定义处理器
1. 继承`BaseProcessor`抽象基类
2. 实现`process`方法，接收`PipelineContext`参数，返回修改后的`PipelineContext`
3. 在`process`方法开头明确声明输入字段来源，结尾明确声明输出字段
4. 异常处理：可预见的异常使用`context.add_error()`记录，不可预见的异常直接抛出
### 字段扩展约定
- 新增字段需遵守小写蛇形命名法
- 字段含义明确，避免与现有字段冲突
- 重要字段需在本文档中更新说明
---
## 五、常见问题
### Q: 如何处理大视频（超过10分钟）？
A: 可以调整`VideoSplitProcessor`的`slice_duration`参数，增大分片时长（如10秒），减少分片数量。也可以在流水线中加入分片采样逻辑，只处理关键帧分片。
### Q: 如何加速处理速度？
A: 视频理解环节可以改为并行调用大模型接口，目前是串行处理，后续可以优化为异步并行。
### Q: 向量数据库中的数据如何查询？
A: 分片向量和整体向量都带有`data_type`元字段（`video_slice`或`video_overall`），可以通过该字段过滤查询。同时`video_id`字段可以关联到具体视频。
