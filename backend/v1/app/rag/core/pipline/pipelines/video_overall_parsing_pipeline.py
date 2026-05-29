from typing import List, Optional

from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    SchemaValidationProcessor,
    VideoAggregationProcessor,
    VideoOverallUnderstandingProcessor,
    VideoGenerateProcessor,
    VectorizationProcessor,
)


class VideoOverallParsingPipeline(BasePipeline):
    """
    视频整体理解流水线
    适用于已经完成视频拆分和分片理解的场景，输入为校验通过的分片数据，流程：
    结果聚合 → 整体理解 → 整体JSON生成 → 整体结构校验 → 整体向量化
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 video_schema_path: Optional[str] = None,
                 enable_vectorization: bool = True):
        """
        初始化视频整体理解流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param video_schema_path: 视频整体校验Schema路径，可选，优先使用该路径而非默认模板
        :param enable_vectorization: 是否启用向量化存储，默认True
        """
        if custom_processors:
            processors = custom_processors
        else:
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
                        data_key="embed_video",
                        store_type="video",  # 视频类型，存入video_knowledge集合
                        id_key="video_id",
                        image_key=None  # 整体向量化不需要处理图片
                    ),
                ])

        super().__init__(processors)
