from typing import Dict, List
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext


class VideoAggregationProcessor(BaseProcessor):
    """
    视频分片聚合处理器
    将所有分片的理解结果聚合，为视频整体理解提供结构化的输入
    """

    def __init__(self):
        """
        初始化视频聚合处理器
        """
        pass

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频分片聚合逻辑

        输入（从上下文获取）：
        - understood_slices: List[Dict] 理解后的分片结构化数据（VideoUnderstandingProcessor输出）
        - valid_slices: List[Dict] 校验通过的分片数据（SchemaValidationProcessor输出，可选）
        - video_id: str 视频ID（初始输入）
        - video_duration: int 视频总时长（毫秒，初始输入）

        输出（写入上下文）：
        - aggregated_video_data: Dict 聚合后的视频完整数据，包含所有分片信息
        - segment_list: List[Dict] 分片索引列表，供整体理解使用
        """
        # 优先使用校验通过的分片，如果没有则使用所有理解后的分片
        valid_slices = context.get("valid_slices", [])
        all_slices = context.get("understood_slices", [])
        slices = valid_slices if valid_slices else all_slices

        if not slices:
            raise ValueError("No slices found in context for aggregation")

        video_id = context.get("video_id")
        video_duration = context.get("video_duration", 0)

        # 构建分片索引列表
        segment_list = []
        all_script_lines = []

        for slice_info in slices:
            understanding = slice_info.get("understanding", {})
            # 收集所有台词
            script_lines = understanding.get("创作要素", {}).get("台词", "")
            if script_lines:
                all_script_lines.append(script_lines)

            # 构建分片索引项
            segment_item = {
                "slice_id": slice_info["slice_id"],
                "slice_index": slice_info["slice_index"],
                "template_name": understanding.get("模板名称", ""),
                "template_type": understanding.get("模板类型", ""),
                "content_summary": understanding.get("生成Prompt完整模板", "")[:100]  # 摘要前100字符
            }
            segment_list.append(segment_item)

        # 构建聚合后的完整视频数据
        aggregated_data = {
            "video_id": video_id,
            "video_duration": video_duration,
            "total_slices": len(slices),
            "valid_slices_count": len(valid_slices),
            "segment_list": segment_list,
            "all_script_lines": all_script_lines,
            "slices_detail": slices  # 完整的分片详情
        }

        # 存储到上下文
        context.set("aggregated_video_data", aggregated_data)
        context.set("segment_list", segment_list)
        context.set("all_script_lines", all_script_lines)

        return context


class VideoGenerateProcessor(BaseProcessor):
    """
    视频整体JSON生成处理器
    根据整体理解结果生成符合模板要求的视频结构化数据，保存在上下文中
    """

    def __init__(self):
        """
        初始化视频生成处理器
        """
        pass

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频JSON生成逻辑

        输入（从上下文获取）：
        - ai_features: Dict 视频整体理解结果（VideoOverallUnderstandingProcessor输出）
        - aggregated_video_data: Dict 聚合后的视频数据（VideoAggregationProcessor输出）
        - video_id: str 视频ID（初始输入）

        输出（写入上下文）：
        - video_data: Dict 视频结构化数据，符合Schema校验要求
        - video_file: None 保留字段，兼容旧接口
        """
        ai_features = context.get("ai_features", {})
        aggregated_data = context.get("aggregated_video_data", {})
        video_id = context.get("video_id")

        if not ai_features:
            raise ValueError("No video understanding result found in context, please ensure VideoOverallUnderstandingProcessor executed successfully")

        # 构建符合模板的JSON结构
        video_json = {
            "video_id": video_id,
            "视频基本信息": ai_features.get("视频基本信息", {}),
            "片段索引列表": aggregated_data.get("segment_list", []),
            "片段间关系": ai_features.get("片段间关系", {}),
            "分片详情": aggregated_data.get("slices_detail", [])
        }

        # 存储到上下文（不再写入本地文件）
        context.set("video_file", None)  # 保留字段，兼容旧接口
        context.set("video_data", video_json)
        context.metadata["video_generated"] = True

        return context
