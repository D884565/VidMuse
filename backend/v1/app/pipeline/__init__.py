# 导出核心抽象
from .base import PipelineContext, BaseProcessor, BasePipeline

# 导出处理器
from .processors import (
    VideoSplitProcessor,
    VideoUnderstandingProcessor,
    SchemaValidationProcessor,
    ProductUnderstandingProcessor,
    ProductGenerateProcessor,
    VectorizationProcessor,
    VideoOverallUnderstandingProcessor,
    VideoGenerateProcessor,
    VideoAggregationProcessor,
    AudioInfoExtractProcessor,
    AudioASRProcessor,
    AudioClassificationProcessor,
    AudioResultAggregator
)

# 导出流水线
from .pipelines import (
    VideoParsingPipeline,
    ProductParsingPipeline,
    VideoOverallParsingPipeline,
    AudioParsingPipeline
)

# 导出持久化相关
from .dao.pipeline_execution_dao import PipelineExecutionDAO
from backend.v1.app.models.pipeline_execution import PipelineExecution, PipelineExecutionStatus

__all__ = [
    # 核心抽象
    "PipelineContext",
    "BaseProcessor",
    "BasePipeline",

    # 处理器
    "VideoSplitProcessor",
    "VideoUnderstandingProcessor",
    "SchemaValidationProcessor",
    "ProductUnderstandingProcessor",
    "ProductGenerateProcessor",
    "VectorizationProcessor",
    "VideoOverallUnderstandingProcessor",
    "VideoGenerateProcessor",
    "VideoAggregationProcessor",
    "AudioInfoExtractProcessor",
    "AudioASRProcessor",
    "AudioClassificationProcessor",
    "AudioResultAggregator",

    # 流水线
    "VideoParsingPipeline",
    "ProductParsingPipeline",
    "VideoOverallParsingPipeline",
    "AudioParsingPipeline",

    # 持久化相关
    "PipelineExecutionDAO",
    "PipelineExecution",
    "PipelineExecutionStatus"
]
