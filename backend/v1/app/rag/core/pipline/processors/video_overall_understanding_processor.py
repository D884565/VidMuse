from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, TextContent


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
        self.llm_client = llm_client or VolcanoLLM()
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

        输入的分片信息：
        {segment_info}

        请保证所有字段完整，信息不足时可以生成合理的模拟值。
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频整体理解逻辑

        :param context: 流水线上下文，需要包含 aggregated_segments 字段
        :return: 修改后的上下文，包含视频整体理解结果
        """
        aggregated_segments = context.get("aggregated_segments", {})
        video_id = context.get("video_id", "vid_001")
        video_duration = context.get("video_duration", 60000)

        if not aggregated_segments:
            raise ValueError("No aggregated segments found in context")

        # 构建请求prompt
        segment_info_str = str(aggregated_segments["segment_list"])
        prompt = self.prompt_template.format(segment_info=segment_info_str)

        # 构建大模型请求
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content=[TextContent(text="请输出视频整体分析结果")])
            ]
        )

        # 调用大模型（Mock：实际调用时取消注释）
        # response = self.llm_client.chat(request)
        # video_overall_info = response.content

        # Mock 响应（临时使用，实际调用时替换为真实响应）
        video_overall_info = {
            "视频基本信息": {
                "video_id": video_id,
                "tree_id": "020301",
                "商品名称": "法式碎花连衣裙",
                "目标人群": "25-35岁都市女性",
                "总时长_ms": video_duration,
                "$剧本scheme": "/",
                "原片核心文案": aggregated_segments.get("all_copies", [])
            },
            "片段索引列表": aggregated_segments.get("segment_list", []),
            "片段间关系": {
                "转场序列": ["硬切"] * (len(aggregated_segments["segment_list"]) - 1),
                "情绪曲线": ["高涨→平稳", "平稳→微升"],
                "视觉节奏": "中景→近景→中景（无剧烈跳变）",
                "BGM节奏匹配": "前5秒卡点重音，中段平缓过渡"
            }
        }

        context.set("video_overall_info", video_overall_info)
        return context
