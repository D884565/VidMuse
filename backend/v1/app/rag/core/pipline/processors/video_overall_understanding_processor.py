import json
import os
from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, TextContent, TextUnderstandingRequest
from backend.v1.app.rag.core.pipline.utils import load_template
from backend.v1.app.rag.core.pipline.utils.json_flattener import JsonFlattener


class VideoOverallUnderstandingProcessor(BaseProcessor):
    """
    视频整体理解处理器
    基于聚合后的分片结果，对整个视频进行整体分析
    """

    def __init__(self, llm_client=None):
        """
        初始化视频整体理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        self.prompt_template = """
        请基于以下视频分片的解析结果，对整个视频进行整体分析，输出结构化的视频信息，严格按照JSON格式返回。

        需要包含以下字段：
        1. 视频基本信息：
           - video_id: 视频ID
           - 商品名称: 视频推广的商品名称
           - 目标人群: 视频的目标受众
           - 总时长_ms: 视频总时长（毫秒）
           - 原片核心文案: 视频中出现的核心台词数组

        2. 片段索引列表：直接使用输入中的segment_list数组，无需修改

        3. 片段间关系：
           - 转场序列: 各片段之间的转场方式数组，如["硬切", "叠化"]
           - 情绪曲线: 视频的情绪变化曲线数组，如["高涨→平稳", "平稳→微升"]
           - 视觉节奏: 整体视觉节奏描述
           - BGM节奏匹配: BGM与画面的匹配情况描述
        

        请严格按照如下json格式输出解析内容，请保证所有字段完整。
        {json_template}
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频整体理解逻辑

        输入（从上下文获取）：
        - aggregated_video_data: Dict 聚合后的视频完整数据（VideoAggregationProcessor输出）
        - segment_list: List[Dict] 分片索引列表（VideoAggregationProcessor输出）
        - all_script_lines: List[str] 所有分片的台词列表（VideoAggregationProcessor输出）
        - video_id: str 视频ID（初始输入）
        - video_duration: int 视频总时长（毫秒，初始输入）

        输出（写入上下文）：
        - ai_features: Dict 视频整体理解结构化结果
        - embed_video: str 扁平化后的视频整体数据，用于向量化
        """
        aggregated_data = context.get("aggregated_video_data", {})
        segment_list = context.get("segment_list", [])
        all_script_lines = context.get("all_script_lines", [])
        video_id = context.get("video_id")
        video_duration = context.get("video_duration", 0)

        if not aggregated_data or not segment_list:
            raise ValueError("No aggregated video data found in context, please ensure VideoAggregationProcessor executed successfully")

        # 构建结构化的分片信息文本
        segment_info_lines = []
        for i, segment in enumerate(segment_list):
            segment_info_lines.append(
                f"分片{i+1}(ID:{segment['slice_id']}): 模板类型={segment['template_type']}, 模板名称={segment['template_name']}, 内容摘要={segment['content_summary']}"
            )
        segment_info_str = "\n".join(segment_info_lines)

        # 构建完整的输入文本
        full_input = f"""
视频ID: {video_id}
视频总时长: {video_duration}ms
总分片数: {len(segment_list)}

所有台词:
{chr(10).join(all_script_lines)}

分片详情:
{segment_info_str}
"""

        # json模板信息注入到prompt
        prompt = self.prompt_template.format(json_template=json.dumps(load_template("video"), ensure_ascii=False))

        # 构建大模型请求
        response = self.llm_client.text_understanding(TextUnderstandingRequest(
            prompt=prompt,
            text=full_input
        ))

        # 解析返回结果
        try:
            resolve = json.loads(response.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Video overall understanding result parse failed: {str(e)}")

        # 补充视频基础信息
        if "视频基本信息" in resolve:
            resolve["视频基本信息"]["video_id"] = video_id
            resolve["视频基本信息"]["总时长_ms"] = video_duration
            resolve["视频基本信息"]["原片核心文案"] = all_script_lines

        # 扁平化结果用于向量化
        # 先添加video_id到结果中，再扁平化
        resolve_with_id = resolve.copy()
        resolve_with_id["video_id"] = video_id
        embed_video = JsonFlattener.flatten(resolve_with_id)

        # 存储到上下文
        context.set("ai_features", resolve)
        context.set("embed_video", embed_video)

        return context
