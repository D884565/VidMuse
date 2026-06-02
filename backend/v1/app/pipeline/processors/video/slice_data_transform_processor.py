from typing import Dict, List
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.v1.app.pipeline.utils import prompt_manager


class SliceDataTransformProcessor(BaseProcessor):
    """
    分片数据转换处理器
    将VideoUnderstandingProcessor输出的理解结果转换为符合Schema要求的分片数据格式
    替代原有的匿名处理器，提供更好的可维护性和错误处理
    """

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行分片数据转换逻辑

        输入（从上下文获取）：
        - understood_slices: List[Dict] 理解后的分片结构化数据（VideoUnderstandingProcessor输出）

        输出（写入上下文）：
        - slice_data: List[Dict] 转换后的分片数据，符合slice Schema要求
        - slice_files: List 空列表，保持接口兼容性
        """
        understood_slices = context.get(constants.UNDERSTOOD_SLICES, [])

        if not understood_slices:
            raise ValueError("No understood slices found in context for transformation")

        slice_data = []
        for slice_info in understood_slices:
            # 验证必要字段存在
            required_fields = ["slice_id", "video_id", "slice_index", "slice_url", "cover_url", "understanding"]
            for field in required_fields:
                if field not in slice_info:
                    raise ValueError(f"Slice missing required field: {field}")

            understanding = slice_info["understanding"]

            # 构建符合Schema要求的分片数据
            transformed_slice = {
                "slice_id": slice_info["slice_id"],
                "video_id": slice_info["video_id"],
                "slice_index": slice_info["slice_index"],
                "slice_url": slice_info["slice_url"],
                "cover_url": slice_info["cover_url"],
                prompt_manager.FIELD_SLICE_TEMPLATE: understanding
            }

            slice_data.append(transformed_slice)

        # 存储结果到上下文
        context.set(constants.SLICE_DATA, slice_data)
        context.set(constants.SLICE_FILES, [])  # 空列表，保持与旧接口的兼容性

        return context
