from typing import Dict, List

from backend.providers import VolcanoLLM, TextUnderstandingRequest
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class VideoAggregationProcessor(BaseProcessor):
    """
    视频分片结果聚合处理器
    将多个分片的解析结果聚合在一起，为整体理解做准备
    """


    def __int__(self):
        self.llm = VolcanoLLM(key=None, model_name=None)
        self.prompt = """
        请基于以下视频分片的解析结果，对视频进行整体分析，输出结构化的视频信息，严格按照JSON格式返回。

        需要包含以下字段：
        1. 视频基本信息：
           - video_id: 视频ID
           - video_duration: 视频时长（毫秒）
        2. 视频分片信息：
           - slice_id: 分片ID
           - slice_start: 分片开始时间（毫秒）
           - slice_end: 分片结束时间（毫秒）
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行分片结果聚合逻辑

        :param context: 流水线上下文，需要包含 slices 或 valid_slices 字段
        :return: 修改后的上下文，包含聚合后的分片信息
        """
        # 优先使用校验通过的切片，如果没有则使用所有切片
        slices = context.get("valid_slices", []) or context.get("slices", [])
        slices_aggr = str([sl for sl in slices])

        if not slices:
            raise ValueError("No slices found in context for aggregation")
        response = self.llm.text_understanding(TextUnderstandingRequest(prompt=self.prompt, text=slices_aggr))
        context.set("VideoAggregation",response.content)


        return context
