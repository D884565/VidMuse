from typing import List, Optional


from backend.v1.app.pipeline.base import BasePipeline, BaseProcessor, constants
from backend.v1.app.pipeline.processors import (

    SchemaValidationProcessor,
    SliceDataTransformProcessor,
)
from backend.v1.app.pipeline.processors.video import VideoSplitProcessor, VideoUnderstandingProcessor, \
    VectorizationProcessor, VideoAggregationProcessor, VideoOverallUnderstandingProcessor, VideoGenerateProcessor


class VideoParsingPipeline(BasePipeline):
    """
    视频解析流水线
    完整端到端流程：视频拆分 → 分片理解 → 切片JSON生成 → 分片结构校验 → 分片向量化 → 结果聚合 → 整体理解 → 整体JSON生成 → 整体结构校验 → 整体向量化
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 slice_schema_path: Optional[str] = None,
                 video_schema_path: Optional[str] = None,
                 enable_vectorization: bool = True,
                 **kwargs):
        """
        初始化视频解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param slice_schema_path: 切片校验Schema路径，可选，优先使用该路径而非默认模板
        :param video_schema_path: 视频整体校验Schema路径，可选，优先使用该路径而非默认模板
        :param enable_vectorization: 是否启用向量化存储，默认True
        :param kwargs: 其他参数，传递给父类
        """
        if custom_processors:
            processors = custom_processors
        else:
            # 构建切片校验器
            if slice_schema_path:
                slice_validator = SchemaValidationProcessor(
                    schema_path=slice_schema_path,
                    data_key=constants.SLICE_DATA,
                    valid_key=constants.VALID_SLICES,
                    invalid_key=constants.INVALID_SLICES,
                    summary_key=constants.SLICE_VALIDATION_SUMMARY,
                    id_field=constants.SLICE_ID
                )
            else:
                # 使用默认slice模板，参数完全匹配原有配置
                slice_validator = SchemaValidationProcessor.for_slice(
                    valid_key=constants.VALID_SLICES,
                    invalid_key=constants.INVALID_SLICES,
                    summary_key=constants.SLICE_VALIDATION_SUMMARY
                )

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

            # 默认处理器顺序：完整的端到端流程（移除SliceGenerateProcessor，使用正式的转换器）
            processors = [
                # 第一阶段：视频拆分
                VideoSplitProcessor(),
                # 第二阶段：分片理解
                VideoUnderstandingProcessor(),
                # 第三阶段：分片数据格式转换（替代SliceGenerateProcessor，不写入本地文件）
                SliceDataTransformProcessor(),
                # 第四阶段：分片结构校验
                slice_validator,
            ]

            # 第五阶段：分片向量化（可选）
            if enable_vectorization:
                processors.extend([
                    # 分片向量化：仅对文本内容进行向量化，存入slice知识库
                    VectorizationProcessor(
                        data_key=constants.EMBED_SLICES,
                        image_key=None,  # 不需要处理图片
                        store_type="slice",  # 分片类型，存入slice_knowledge集合
                        id_key=constants.SLICE_ID
                    ),
                ])

            # 第六阶段：结果聚合
            processors.extend([
                VideoAggregationProcessor(),
            ])

            # 第七阶段：整体理解
            processors.extend([
                VideoOverallUnderstandingProcessor(),
            ])

            # 第八阶段：整体JSON生成
            processors.extend([
                VideoGenerateProcessor(),
            ])

            # 第九阶段：整体结构校验
            processors.extend([
                video_validator,
            ])

            # 第十阶段：整体向量化（可选）
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

        super().__init__(processors, pipeline_type="video", **kwargs)
