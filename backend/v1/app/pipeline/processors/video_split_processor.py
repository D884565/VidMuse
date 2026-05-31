from typing import Dict, List
import io
import tempfile
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

    def __init__(self, slice_duration: int = 10000):
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

            # 分割视频，加载为字节流（不保留临时文件）
            segments = ffmpeg_tool.split_video(
                video_path=video_path,
                segment_duration=self.slice_duration / 1000,  # 转换为秒
                extract_first_frame=True,
                frame_format="jpg",
                load_as_bytes=True,
                keep_files=False
            )
        slices = list()
        idx = 0
        images = list()
        slices_images_name = list()
        slices_video_name = list()
        # todo 后续异步落库
        for segment in segments:
            if not segment.segment_bytes:
                logger.warning(f"跳过空的视频片段 {idx}")
                continue

            # 对象存储name
            slice_chunk_name = object_name + f"_slice_{idx}.mp4"
            slice_img_name = object_name + f"_slice_{idx}.jpg"  # 使用正确的图片扩展名
            slices_images_name.append(slice_img_name)
            slices_video_name.append(slice_chunk_name)

            # url
            slices.append(client.upload_fileobj(io.BytesIO(segment.segment_bytes), slice_chunk_name))

            if segment.frame_bytes:
                images.append(client.upload_fileobj(io.BytesIO(segment.frame_bytes), slice_img_name))
            else:
                logger.warning(f"视频片段 {idx} 没有提取到首帧，使用空值")
                images.append(None)

            idx += 1




        context.set(constants.SLICE_COUNT, len(slices))
        context.set(constants.SLICES_URL, slices)
        context.set(constants.IMAGES_URL, images)
        context.set(constants.SLICES_OBJECT_NAME, slices_video_name)
        context.set(constants.IMAGES_OBJECT_NAME, slices_images_name)
        return context
