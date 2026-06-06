# 相似爆款视频检索工具使用说明

## 功能概述

相似爆款视频检索工具是一个基于向量检索的Agent工具，可以根据输入的视频解析报告，从`video_knowledge`向量库中检索相似的爆款视频分析报告，为剧本创作提供参考。

## 工具特性

- **基于向量检索**：使用向量数据库进行语义相似度匹配，检索结果更准确
- **多维度返回**：返回相似视频的创意、脚本结构、数据表现、标签、分类等完整信息
- **灵活配置**：支持自定义返回数量、相似度阈值等参数
- **无缝集成**：已自动注册到ScriptAgent中，可以直接在剧本生成流程中使用

## 直接调用方式

```python
from backend.v1.app.agent.tools.similar_video_search_tool import SimilarVideoSearchTool

# 初始化工具
tool = SimilarVideoSearchTool()

# 准备视频解析报告
video_report = """
视频解析报告：
视频主题：iPhone 15 开箱测评
视频类型：数码测评
受众群体：数码爱好者、换机用户
核心卖点：钛金属边框、A17 Pro芯片、USB-C接口
视频结构：
- 开头0-3s：特写iPhone 15包装盒，配文案"最新iPhone 15开箱！"
- 中间3-15s：开箱过程，展示外观设计和细节
- 中间15-30s：性能测试，跑分和游戏表现
- 结尾30-35s：总结优缺点，给出购买建议
数据表现：播放量120万，点赞8.5万，评论1.2万，转发5000
标签：#iPhone15 #数码测评 #开箱
"""

# 执行检索
result = tool.execute({
    "video_report": video_report,  # 必填：视频解析报告内容
    "top_k": 5,                    # 可选：返回结果数量，默认5
    "min_score": 0.6               # 可选：最低相似度阈值，0-1，默认0.6
})

# 解析结果
import json
result_data = json.loads(result)
if result_data["status"] == "success":
    print(f"找到{result_data['total_results']}条相似视频：")
    for video in result_data["similar_videos"]:
        print(f"相似度：{video['similarity_score']}")
        print(f"标题：{video.get('video_title', '无标题')}")
        print(f"热度：{video.get('hot_score', 'N/A')}")
        print(f"播放量：{video.get('play_count', 'N/A')}")
        print(f"内容：{video['content'][:100]}...")
        print("---")
```

## 在ScriptAgent中使用

### 方式1：自动检测使用
当调用`generate_script`方法时，如果传入了`video_report`参数，ScriptAgent会自动检测到并在合适的时机调用相似视频检索工具获取参考。

```python
from backend.v1.app.agent.implementations.script_agent import script_agent

# 项目信息
project_info = {
    "title": "iPhone 15 带货视频",
    "description": "新款iPhone 15手机带货短视频",
    "product_info": "iPhone 15，钛金属边框，A17 Pro芯片，USB-C接口",
    "target_audience": "数码爱好者，年轻用户",
    "style": "科技感，年轻化"
}

# 参考视频报告
video_report = """
这里放视频解析报告内容...
"""

# 生成剧本（自动使用相似视频参考）
script = await script_agent.generate_script(
    project_info=project_info,
    target_duration=30,
    video_report=video_report,  # 传入视频报告
    output_format="要求输出JSON格式..."
)
```

### 方式2：指定创作模式
可以显式指定使用`similar_video`创作模式：

```python
script = await script_agent.generate_script(
    project_info=project_info,
    target_duration=30,
    creation_mode="similar_video",  # 指定使用相似视频模式
    video_report=video_report,
    output_format="要求输出JSON格式..."
)
```

## 工具返回字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| status | string | 执行状态，success/error |
| query_length | integer | 输入报告的长度 |
| total_results | integer | 返回的相似视频数量 |
| similar_videos | array | 相似视频列表 |
| similar_videos[].result_id | string | 结果唯一ID |
| similar_videos[].similarity_score | float | 相似度得分，0-1之间，越高越相似 |
| similar_videos[].content | string | 视频报告完整内容 |
| similar_videos[].source_type | string | 来源类型 |
| similar_videos[].video_title | string | 视频标题（从metadata中提取） |
| similar_videos[].hot_score | float | 视频热度分数（从metadata中提取） |
| similar_videos[].play_count | integer | 播放量（从metadata中提取） |
| similar_videos[].like_count | integer | 点赞数（从metadata中提取） |
| similar_videos[].comment_count | integer | 评论数（从metadata中提取） |
| similar_videos[].share_count | integer | 转发数（从metadata中提取） |
| similar_videos[].tags | array | 视频标签（从metadata中提取） |
| similar_videos[].category | string | 视频分类（从metadata中提取） |
| similar_videos[].metadata | object | 完整的元数据信息 |

## 注意事项

1. **向量库依赖**：使用前需要确保`video_knowledge`向量集合已经存在，并且已经导入了足够的爆款视频分析报告数据
2. **向量生成**：检索时需要自动生成查询向量，确保系统已经正确配置了embedding服务
3. **性能考虑**：向量检索是CPU/GPU密集型操作，高并发场景下建议添加缓存
4. **数据质量**：检索效果取决于向量库中数据的质量和丰富度，建议定期更新和维护向量库数据

## 常见问题

### Q: 工具初始化失败怎么办？
A: 检查SearchEngine依赖是否正确安装，向量数据库连接配置是否正确，`video_knowledge`集合是否存在。

### Q: 检索结果为空怎么办？
A: 可以适当降低`min_score`阈值，或者检查向量库中是否有相关领域的视频数据。

### Q: 如何提高检索准确率？
A: 提供更详细、结构更完整的视频解析报告，确保向量库中的数据格式与输入报告格式一致。
