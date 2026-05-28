from typing import List, Optional

from backend.v1.app.rag.core.pipline import VectorizationProcessor
from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    VideoSplitProcessor,
    VideoUnderstandingProcessor,
    SchemaValidationProcessor,
    VideoOverallUnderstandingProcessor,
)


class VideoParsingPipeline(BasePipeline):
    """
    视频解析流水线
    完整端到端流程：视频拆分 → 分片理解 → 切片JSON生成 → 分片结构校验 → 结果聚合 → 整体理解 → 整体JSON生成 → 整体结构校验
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 slice_schema_path: Optional[str] = None,
                 video_schema_path: Optional[str] = None):
        """
        初始化视频解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param slice_schema_path: 切片校验Schema路径，可选，优先使用该路径而非默认模板
        :param video_schema_path: 视频整体校验Schema路径，可选，优先使用该路径而非默认模板
        """
        if custom_processors:
            processors = custom_processors
        else:
            # 构建切片校验器
            if slice_schema_path:
                slice_validator = SchemaValidationProcessor(
                    schema_path=slice_schema_path,
                    data_key="slice_data",
                    valid_key="valid_slices",
                    invalid_key="invalid_slices",
                    summary_key="slice_validation_summary",
                    id_field="slice_id"
                )
            else:
                # 使用默认slice模板，参数完全匹配原有配置
                slice_validator = SchemaValidationProcessor.for_slice(
                    valid_key="valid_slices",
                    invalid_key="invalid_slices",
                    summary_key="slice_validation_summary"
                )

            # 构建视频整体校验器
            if video_schema_path:
                video_validator = SchemaValidationProcessor(
                    schema_path=video_schema_path,
                    data_key="video_data",
                    valid_key="valid_video",
                    invalid_key="invalid_video",
                    summary_key="video_validation_summary",
                    id_field="video_id"
                )
            else:
                # 使用默认video模板，自定义参数
                video_validator = SchemaValidationProcessor.for_video(
                    valid_key="valid_video",
                    invalid_key="invalid_video",
                    summary_key="video_validation_summary",
                    id_field="video_id"
                )

            # 默认处理器顺序：完整的端到端流程
            processors = [
                # 第一阶段：视频拆分和分片理解
                VideoSplitProcessor(),
                VideoUnderstandingProcessor(),
                # todo 后期规则模板校验
                # slice_validator,
                # 分片向量处理
                VectorizationProcessor(data_key="embed_slices"),
                # 第二阶段：整体理解
                VideoOverallUnderstandingProcessor(),
                # video_validator   # 校验整体视频结构
                VectorizationProcessor(data_key="embed_video"),
            ]

        super().__init__(processors)
