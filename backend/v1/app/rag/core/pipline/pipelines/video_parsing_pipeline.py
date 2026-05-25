from typing import List
from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    VideoSplitProcessor,
    VideoUnderstandingProcessor,
    SliceGenerateProcessor,
    SchemaValidationProcessor
)


class VideoParsingPipeline(BasePipeline):
    """
    视频解析流水线
    第一条流水线：视频拆分 → 大模型理解 → JSON生成 → 结构校验
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None):
        """
        初始化视频解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        """
        if custom_processors:
            processors = custom_processors
        else:
            # 默认处理器顺序
            processors = [
                VideoSplitProcessor(),
                VideoUnderstandingProcessor(),
                SliceGenerateProcessor(),
                SchemaValidationProcessor()
            ]

        super().__init__(processors)
