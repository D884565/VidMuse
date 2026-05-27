from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, TextContent, TextUnderstandingRequest


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

        if not aggregated_segments:
            raise ValueError("No aggregated segments found in context")

        # 构建请求prompt
        segment_info_str = str(aggregated_segments["segment_list"])
        prompt = self.prompt_template.format(segment_info=segment_info_str)

        # 构建大模型请求
        response = self.llm_client.text_understanding(TextUnderstandingRequest(prompt=self.prompt_template, text=aggregated_segments))
        context.set("ai_features", response.content)
        return context
