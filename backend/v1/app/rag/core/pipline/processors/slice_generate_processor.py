import os
import json
from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class SliceGenerateProcessor(BaseProcessor):
    """
    切片JSON生成处理器
    根据大模型理解结果生成符合模板要求的slice.json文件
    """

    def __init__(self, output_dir: str = None):
        """
        初始化切片生成处理器

        :param output_dir: 生成的JSON文件输出目录，默认使用项目内的resources/resolve目录
        """
        if output_dir is None:
            # 动态构建输出目录路径，适配不同操作系统
            current_dir = os.path.abspath(__file__)
            # 从当前文件向上找到项目根目录（通过查找.git目录或requirements.txt判断）
            project_root = current_dir
            max_depth = 15
            while max_depth > 0:
                # 优先查找项目根目录的标志性文件/目录
                if (os.path.exists(os.path.join(project_root, ".git")) or
                    os.path.exists(os.path.join(project_root, "requirements.txt")) or
                    os.path.exists(os.path.join(project_root, "pyproject.toml"))):
                    # 检查根目录下是否有resources目录
                    if os.path.exists(os.path.join(project_root, "resources")):
                        break
                project_root = os.path.dirname(project_root)
                max_depth -= 1
            if max_depth == 0:
                # 如果没有找到标志性文件，回退到查找最近的resources目录
                project_root = current_dir
                max_depth = 15
                while max_depth > 0 and not os.path.exists(os.path.join(project_root, "resources")):
                    project_root = os.path.dirname(project_root)
                    max_depth -= 1
                if max_depth == 0:
                    raise RuntimeError("Could not find project root directory with resources folder")
            output_dir = os.path.join(project_root, "resources", "resolve")

        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行切片JSON生成逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含生成的文件路径和数据
        """
        understood_slices = context.get("understood_slices", [])

        if not understood_slices:
            raise ValueError("No understood slices found in context")

        slice_files: List[str] = []
        slice_data: List[Dict] = []

        for slice_info in understood_slices:
            # 构建符合模板的JSON结构
            slice_json = {
                "slice_id": slice_info["slice_id"],
                "time_range": slice_info["time_range"],
                "video_id": slice_info["video_id"],
                "单片段模板": slice_info["understanding"]
            }

            # 生成文件名
            file_name = f"{slice_info['video_id']}_{slice_info['slice_id']}.json"
            file_path = os.path.join(self.output_dir, file_name)

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(slice_json, f, ensure_ascii=False, indent=2)

            slice_files.append(file_path)
            slice_data.append(slice_json)

        context.set("slice_files", slice_files)
        context.set("slice_data", slice_data)
        context.metadata["generated_count"] = len(slice_files)

        return context
