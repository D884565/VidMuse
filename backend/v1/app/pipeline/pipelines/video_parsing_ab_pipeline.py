from typing import List, Optional

from backend.v1.app.pipeline.base import BaseProcessor, constants
from backend.v1.app.pipeline.pipelines.video_parsing_pipeline import VideoParsingPipeline
from backend.v1.app.pipeline.processors.video.video_keyframe_audio_understanding_processor import VideoKeyframeAudioUnderstandingProcessor


class VideoParsingABPipeline(VideoParsingPipeline):
    """
    视频解析流水线AB测试版本
    使用关键帧+音频识别的理解方式替代原有的视频分片理解方式，后续处理逻辑与原流水线完全一致
    接口与原VideoParsingPipeline完全兼容，可以无缝切换进行AB测试
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 slice_schema_path: Optional[str] = None,
                 video_schema_path: Optional[str] = None,
                 enable_vectorization: bool = True,
                 scene_threshold: float = 0.3,
                 max_keyframes: int = 20,
                 min_keyframes: int = 3,
                 **kwargs):
        """
        初始化AB测试视频解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param slice_schema_path: 切片校验Schema路径，可选，优先使用该路径而非默认模板
        :param video_schema_path: 视频整体校验Schema路径，可选，优先使用该路径而非默认模板
        :param enable_vectorization: 是否启用向量化存储，默认True
        :param scene_threshold: 场景变化检测阈值，0-1之间，越大越严格，关键帧越少
        :param max_keyframes: 最大关键帧数量，避免过多关键帧导致成本过高
        :param min_keyframes: 最小关键帧数量，避免过短视频内容过少
        :param kwargs: 其他参数，传递给父类
        """
        # 如果没有自定义处理器，使用默认的处理器链，仅替换VideoUnderstandingProcessor
        if not custom_processors:
            # 先调用父类初始化获取默认处理器链
            super().__init__(
                slice_schema_path=slice_schema_path,
                video_schema_path=video_schema_path,
                enable_vectorization=enable_vectorization,
                **kwargs
            )

            # 替换VideoUnderstandingProcessor为VideoKeyframeAudioUnderstandingProcessor
            new_processors = []
            for processor in self.processors:
                if processor.__class__.__name__ == "VideoUnderstandingProcessor":
                    # 替换为新的理解处理器
                    new_processor = VideoKeyframeAudioUnderstandingProcessor(
                        scene_threshold=scene_threshold,
                        max_keyframes=max_keyframes,
                        min_keyframes=min_keyframes
                    )
                    new_processors.append(new_processor)
                else:
                    # 保留其他处理器不变
                    new_processors.append(processor)

            # 更新处理器链
            self.processors = new_processors
        else:
            # 如果提供了自定义处理器，直接使用父类初始化
            super().__init__(
                custom_processors=custom_processors,
                slice_schema_path=slice_schema_path,
                video_schema_path=video_schema_path,
                enable_vectorization=enable_vectorization,
                **kwargs
            )

        # 重写流水线类型标识
        self.pipeline_type = "video_ab"
