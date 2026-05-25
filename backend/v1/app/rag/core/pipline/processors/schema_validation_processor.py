import json
import os
from typing import Dict, List, Tuple
from jsonschema import validate, ValidationError
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class SchemaValidationProcessor(BaseProcessor):
    """
    结构校验处理器
    使用JSON Schema校验生成的slice.json文件结构是否符合要求
    """

    def __init__(self, schema_path: str = None):
        """
        初始化结构校验处理器

        :param schema_path: JSON Schema文件路径，默认使用项目内的slice_valid.json
        """
        if schema_path is None:
            # 动态构建schema文件路径，适配不同操作系统
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
            schema_path = os.path.join(project_root, "resources", "template", "resolve", "valid_template", "slice_valid.json")
        self.schema = self._load_schema(schema_path)

    def _load_schema(self, schema_path: str) -> Dict:
        """
        加载JSON Schema文件

        :param schema_path: Schema文件路径
        :return: Schema字典
        """
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_slice(self, slice_data: Dict) -> Tuple[bool, str]:
        """
        校验单个切片数据是否符合Schema要求

        :param slice_data: 切片数据
        :return: (是否通过校验, 错误信息)
        """
        try:
            validate(instance=slice_data, schema=self.schema)
            return True, ""
        except ValidationError as e:
            return False, e.message

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行结构校验逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含校验结果
        """
        slice_data = context.get("slice_data", [])

        if not slice_data:
            raise ValueError("No slice data found in context")

        valid_slices: List[Dict] = []
        invalid_slices: List[Dict] = []

        for data in slice_data:
            is_valid, error = self._validate_slice(data)
            if is_valid:
                valid_slices.append(data)
            else:
                invalid_slices.append({
                    "slice_id": data.get("slice_id", "unknown"),
                    "error": error,
                    "data": data
                })

        context.set("valid_slices", valid_slices)
        context.set("invalid_slices", invalid_slices)
        context.set("validation_summary", {
            "total": len(slice_data),
            "valid": len(valid_slices),
            "invalid": len(invalid_slices)
        })

        return context
