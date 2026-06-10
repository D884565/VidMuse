from typing import List, Optional

from backend.v1.app.pipeline.base import BasePipeline, BaseProcessor, constants
from backend.v1.app.pipeline.processors import (
    SchemaValidationProcessor,
    VectorizationProcessor,
    AssetPersistProcessor,
)
from backend.v1.app.pipeline.processors.video import DirectVideoUnderstandingProcessor


class DirectVideoParsingPipeline(BasePipeline):
    """
    极简视频解析流水线
    流程：完整视频URL → 大模型直接理解 → 输出video.json和slice.json → 校验 → 向量化 → 落库
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 slice_schema_path: Optional[str] = None,
                 video_schema_path: Optional[str] = None,
                 enable_vectorization: bool = True,
                 **kwargs):
        """
        初始化极简视频解析流水线

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
                # 使用默认slice模板
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
                # 使用默认video模板
                video_validator = SchemaValidationProcessor.for_video(
                    valid_key=constants.VALID_VIDEO,
                    invalid_key=constants.INVALID_VIDEO,
                    summary_key=constants.VIDEO_VALIDATION_SUMMARY,
                    id_field=constants.VIDEO_ID
                )

            # 极简处理器顺序
            processors = [
                # 1. 直接理解完整视频，一次性输出所有结构化数据
                DirectVideoUnderstandingProcessor(),
                # 2. 分片格式校验
                slice_validator,
                # 3. 整体格式校验
                video_validator,
            ]

            # 4. 向量化（可选）
            if enable_vectorization:
                processors.extend([
                    # 分片向量化：存入slice知识库
                    VectorizationProcessor(
                        data_key=constants.EMBED_SLICES,
                        image_key=None,
                        store_type="slice",
                        id_key=constants.SLICE_ID
                    ),
                    # 视频整体向量化：存入video知识库
                    VectorizationProcessor(
                        data_key=constants.EMBED_VIDEO,
                        store_type="video",
                        id_key=constants.VIDEO_ID,
                        image_key=None
                    ),
                ])

            # 5. 结果落库到ai_features字段
            processors.append(AssetPersistProcessor())

        super().__init__(processors, pipeline_type="direct_video", **kwargs)
