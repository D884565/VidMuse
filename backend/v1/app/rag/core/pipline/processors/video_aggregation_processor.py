from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class VideoAggregationProcessor(BaseProcessor):
    """
    视频分片结果聚合处理器
    将多个分片的解析结果聚合在一起，为整体理解做准备
    """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行分片结果聚合逻辑

        :param context: 流水线上下文，需要包含 slices 或 valid_slices 字段
        :return: 修改后的上下文，包含聚合后的分片信息
        """
        # 优先使用校验通过的切片，如果没有则使用所有切片
        slices = context.get("valid_slices", []) or context.get("slices", [])
        video_id = context.get("video_id", "vid_001")
        video_duration = context.get("video_duration", 60000)

        if not slices:
            raise ValueError("No slices found in context for aggregation")

        # 构建片段索引列表
        segment_list = []
        all_copies = []
        template_types = []

        for idx, slice_data in enumerate(slices, 1):
            template = slice_data.get("单片段模板", {})
            segment = {
                "slice_id": slice_data.get("slice_id", f"s_{idx:03d}"),
                "time_range_ms": slice_data.get("time_range", [0, 0]),
                "序号": idx,
                "模板类型": template.get("模板类型", "UNKNOWN"),
                "模板名称": template.get("模板名称", ""),
                "机制": template.get("机制", ""),
                "总结": template.get("总结", ""),
                "核心视觉标签": template.get("创作要素", {}).get("画面", "").split("，")
            }
            segment_list.append(segment)
            template_types.append(template.get("模板类型", "UNKNOWN"))

            # 收集所有台词
            if "台词" in template.get("创作要素", {}):
                all_copies.append(template["创作要素"]["台词"])

        # 聚合信息
        aggregated_data = {
            "video_id": video_id,
            "total_duration": video_duration,
            "segment_count": len(segment_list),
            "template_types": template_types,
            "all_copies": all_copies,
            "segment_list": segment_list
        }

        context.set("aggregated_segments", aggregated_data)
        return context
