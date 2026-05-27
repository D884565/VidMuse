from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class VideoSplitProcessor(BaseProcessor):
    """
    视频拆分处理器
    将长视频拆分为多个短视频片段（Mock实现）
    """

    def __init__(self, slice_duration: int = 5000):
        """
        初始化视频拆分处理器

        :param slice_duration: 每个片段的时长，单位毫秒，默认5秒
        """
        self.slice_duration = slice_duration

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频拆分逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含拆分后的片段列表
        """
        video_id = context.get("video_id")

        video_duration = context.get("video_duration", 60000)  # 默认视频时长1分钟（Mock）

        if not video_id:
            raise ValueError("video_id is required in context")

        # Mock 拆分逻辑：按固定时长拆分
        slices: List[Dict] = []
        start_time = 0
        slice_index = 1

        while start_time < video_duration:
            end_time = min(start_time + self.slice_duration, video_duration)
            slices.append({
                "slice_id": f"s_{slice_index:03d}",
                "time_range": [start_time, end_time],
                "video_id": video_id
            })
            start_time = end_time
            slice_index += 1

        context.set("slices", slices)
        context.metadata["split_count"] = len(slices)

        return context
