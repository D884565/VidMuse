from typing import Dict, List

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
import io

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
        :return: 修改后的上下文，包含拆分后的片段url列表
        """

        # 先获取视频（素材）id，从对象存储中查出来，在内存里面分割，然后再上传对象存储，最后返回的是对象存储的url
        video_id = context.get("video_id")
        object_name = context.get("object_name")
        if not object_name:
            raise ValueError("video_id is required in context")

        from backend.store import get_storage_client
        client = get_storage_client()
        ios = client.get_object(object_name)

        from backend.ffmpeg import FFmpegVideoProcessor
        ios = FFmpegVideoProcessor.split_into_segments_in_memory(ios, (10,20))
        slices = list()

        # todo 后续异步落库
        for i, by in enumerate(ios):
            slices.append(client.upload_fileobj(io.BytesIO(by), f"{video_id}_{i}.mp4"))



        context.set("slices", slices)
        context.metadata["split_count"] = len(slices)

        return context
