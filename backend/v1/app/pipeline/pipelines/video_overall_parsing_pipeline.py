from typing import List, Optional

from backend.v1.app.pipeline.base import BasePipeline, BaseProcessor, constants
from backend.v1.app.pipeline.processors import (
    SchemaValidationProcessor,
)
from backend.v1.app.pipeline.processors.video import VideoAggregationProcessor, VideoOverallUnderstandingProcessor, \
    VideoGenerateProcessor, VectorizationProcessor


class VideoOverallParsingPipeline(BasePipeline):
    """
    视频整体理解流水线
    适用于已经完成视频拆分和分片理解的场景，输入为校验通过的分片数据，流程：
    结果聚合 → 整体理解 → 整体JSON生成 → 整体结构校验 → 整体向量化
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 video_schema_path: Optional[str] = None,
                 enable_vectorization: bool = True,
                 **kwargs):
        """
        初始化视频整体理解流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param video_schema_path: 视频整体校验Schema路径，可选，优先使用该路径而非默认模板
        :param enable_vectorization: 是否启用向量化存储，默认True
        :param kwargs: 其他参数，传递给父类
        """
        if custom_processors:
            processors = custom_processors
        else:
            # 构建视频整体校验器
            if video_schema_path:
                video_validator = SchemaValidationProcessor(
                    schema_path=video_schema_path,
                    data_key=constants.VIDEO_DATA,
                    valid_key=constants.VALID_VIDEO,
                    invalid_key=constants.INVALID_VIDEO,
                    summary_key=constants.VIDEO_VALIDATION_SUMMARY,
                    id_field=constants.VIDEO_ID
                )
            else:
                # 使用默认video模板，自定义参数
                video_validator = SchemaValidationProcessor.for_video(
                    valid_key=constants.VALID_VIDEO,
                    invalid_key=constants.INVALID_VIDEO,
                    summary_key=constants.VIDEO_VALIDATION_SUMMARY,
                    id_field=constants.VIDEO_ID
                )

            # 默认处理器顺序
            processors = [
                # 第一阶段：结果聚合
                VideoAggregationProcessor(),
                # 第二阶段：整体理解
                VideoOverallUnderstandingProcessor(),
                # 第三阶段：整体JSON生成
                VideoGenerateProcessor(),
                # 第四阶段：整体结构校验
                video_validator,
            ]

            # 第五阶段：整体向量化（可选）
            if enable_vectorization:
                processors.extend([
                    # 视频整体向量化：存入video知识库
                    VectorizationProcessor(
                        data_key=constants.EMBED_VIDEO,
                        store_type="video",  # 视频类型，存入video_knowledge集合
                        id_key=constants.VIDEO_ID,
                        image_key=None  # 整体向量化不需要处理图片
                    ),
                ])

        super().__init__(processors, pipeline_type="video_overall", **kwargs)
