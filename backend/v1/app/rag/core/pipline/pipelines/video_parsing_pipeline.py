import os
from typing import List
from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    VideoSplitProcessor,
    VideoUnderstandingProcessor,
    SliceGenerateProcessor,
    SchemaValidationProcessor,
    VideoAggregationProcessor,
    VideoOverallUnderstandingProcessor,
    VideoGenerateProcessor
)


class VideoParsingPipeline(BasePipeline):
    """
    视频解析流水线
    完整端到端流程：视频拆分 → 分片理解 → 切片JSON生成 → 分片结构校验 → 结果聚合 → 整体理解 → 整体JSON生成 → 整体结构校验
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 slice_schema_path: str = None,
                 video_schema_path: str = None):
        """
        初始化视频解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param slice_schema_path: 切片校验Schema路径，可选，默认使用slice_valid.json
        :param video_schema_path: 视频整体校验Schema路径，可选，默认使用video_valid.json
        """
        # 处理Schema路径
        if slice_schema_path is None or video_schema_path is None:
            # 动态构建schema文件路径
            current_dir = os.path.abspath(__file__)
            # 从当前文件向上找到项目根目录
            project_root = current_dir
            max_depth = 15
            while max_depth > 0:
                if (os.path.exists(os.path.join(project_root, ".git")) or
                    os.path.exists(os.path.join(project_root, "requirements.txt")) or
                    os.path.exists(os.path.join(project_root, "pyproject.toml"))):
                    if os.path.exists(os.path.join(project_root, "resources")):
                        break
                project_root = os.path.dirname(project_root)
                max_depth -= 1
            if max_depth == 0:
                project_root = current_dir
                max_depth = 15
                while max_depth > 0 and not os.path.exists(os.path.join(project_root, "resources")):
                    project_root = os.path.dirname(project_root)
                    max_depth -= 1
                if max_depth == 0:
                    raise RuntimeError("Could not find project root directory with resources folder")

            if slice_schema_path is None:
                slice_schema_path = os.path.join(
                    project_root, "resources", "template", "resolve", "valid_template", "slice_valid.json"
                )
            if video_schema_path is None:
                video_schema_path = os.path.join(
                    project_root, "resources", "template", "resolve", "valid_template", "video_valid.json"
                )

        if custom_processors:
            processors = custom_processors
        else:
            # 默认处理器顺序：完整的端到端流程
            processors = [
                # 第一阶段：视频拆分和分片理解
                VideoSplitProcessor(),
                VideoUnderstandingProcessor(),
                SliceGenerateProcessor(),
                SchemaValidationProcessor(
                    schema_path=slice_schema_path,
                    data_key="slice_data",
                    valid_key="valid_slices",
                    invalid_key="invalid_slices",
                    summary_key="slice_validation_summary",
                    id_field="slice_id"
                ),  # 校验切片结构

                # 第二阶段：整体理解
                VideoAggregationProcessor(),
                VideoOverallUnderstandingProcessor(),
                VideoGenerateProcessor(),
                SchemaValidationProcessor(
                    schema_path=video_schema_path,
                    data_key="video_data",
                    valid_key="valid_video",
                    invalid_key="invalid_video",
                    summary_key="video_validation_summary",
                    id_field="video_id"
                )   # 校验整体视频结构
            ]

        super().__init__(processors)
