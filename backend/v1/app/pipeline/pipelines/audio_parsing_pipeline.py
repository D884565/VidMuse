from typing import List, Optional

from backend.v1.app.pipeline.base import BasePipeline, BaseProcessor
from backend.v1.app.pipeline.processors import (
    AudioInfoExtractProcessor,
    AudioASRProcessor,
    AudioClassificationProcessor,
    AudioResultAggregator,
)


class AudioParsingPipeline(BasePipeline):
    """
    音频解析流水线
    整合音频信息提取、语音识别、音频分类、结果聚合四个处理器
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None, **kwargs):
        if custom_processors:
            processors = custom_processors
        else:
            processors = [
                AudioInfoExtractProcessor(),
                AudioASRProcessor(),
                AudioClassificationProcessor(),
                AudioResultAggregator()
            ]

        super().__init__(
            processors=processors,
            enable_persistence=True,
            persist_after_each_processor=True,
            persist_on_error=True,
            pipeline_type="AudioParsingPipeline",
            **kwargs
        )
