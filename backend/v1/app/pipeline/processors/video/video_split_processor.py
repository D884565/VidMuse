from typing import Dict, List
import io
import tempfile

from backend.framework.trace import trace
from backend.store import get_storage_client
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.ffmpeg import FFmpegVideoTool
import logging

logger = logging.getLogger(__name__)

class VideoSplitProcessor(BaseProcessor):
    """
    视频拆分处理器
    将长视频拆分为多个短视频片段
    """

    def __init__(self, slice_duration: int = 15000):
        """
        初始化视频拆分处理器

        :param slice_duration: 每个片段的时长，单位毫秒，默认15秒
        """
        self.slice_duration = slice_duration

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频拆分逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含拆分后的片段url列表
        """

        # 先获取视频（素材）id，从对象存储中查出来，写入磁盘分割，然后再上传对象存储，最后返回的是对象存储的url
        video_id = context.get(constants.VIDEO_ID)
        object_name = context.get(constants.OBJECT_NAME)
        if not object_name or not video_id:
            raise ValueError("video_id and object_name are required in context")

        client = get_storage_client()
        video_bytes = client.get_object(object_name)

        # 初始化FFmpeg工具，使用临时目录，自动清理
        with tempfile.TemporaryDirectory(prefix="video_split_") as temp_dir:
            ffmpeg_tool = FFmpegVideoTool(temp_dir=temp_dir, auto_cleanup=True)

            # 将字节流写入临时文件
            video_path = ffmpeg_tool.bytes_to_file(video_bytes, suffix=".mp4")

            # 分割视频，保留在磁盘上（不加载到内存）
            segments = ffmpeg_tool.split_video(
                video_path=video_path,
                segment_duration=self.slice_duration / 1000,  # 转换为秒
                extract_first_frame=False,  # 不需要提取首帧
                load_as_bytes=False,  # 不加载到内存，保留在磁盘上
                keep_files=True  # 保留分割后的文件
            )
            slices = list()
            idx = 0
            slices_video_name = list()
            # todo 后续异步落库
            for segment in segments:
                if not segment.segment_path:
                    logger.warning(f"跳过空的视频片段 {idx}")
                    continue

                # 对象存储name
                slice_chunk_name = object_name + f"_slice_{idx}.mp4"
                slices_video_name.append(slice_chunk_name)

                # 从磁盘文件上传到对象存储（在临时目录删除前完成上传）
                slices.append(client.upload_file(segment.segment_path, slice_chunk_name))

                idx += 1

        context.set(constants.SLICE_COUNT, len(slices))
        context.set(constants.SLICES_URL, slices)
        context.set(constants.SLICES_OBJECT_NAME, slices_video_name)
        return context
