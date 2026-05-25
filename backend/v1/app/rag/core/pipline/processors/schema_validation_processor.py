import json
import os
from typing import Dict, List, Tuple
from jsonschema import validate, ValidationError
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext


class SchemaValidationProcessor(BaseProcessor):
    """
    通用结构校验处理器
    使用JSON Schema校验数据结构是否符合要求，支持切片、商品、视频等多种类型的数据校验
    """

    def __init__(self, schema_path: str = None,
                 data_key: str = "slice_data",
                 valid_key: str = "valid_slices",
                 invalid_key: str = "invalid_slices",
                 summary_key: str = "validation_summary",
                 id_field: str = "slice_id"):
        """
        初始化结构校验处理器

        :param schema_path: JSON Schema文件路径
        :param data_key: 从上下文中获取待校验数据的键名
        :param valid_key: 校验通过数据存储的键名
        :param invalid_key: 校验失败数据存储的键名
        :param summary_key: 校验汇总信息存储的键名
        :param id_field: 数据中唯一标识的字段名，用于错误信息展示
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
        self.data_key = data_key
        self.valid_key = valid_key
        self.invalid_key = invalid_key
        self.summary_key = summary_key
        self.id_field = id_field

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

    def _validate_data(self, data: Dict) -> Tuple[bool, str]:
        """
        校验单个数据是否符合Schema要求

        :param data: 待校验的数据
        :return: (是否通过校验, 错误信息)
        """
        try:
            validate(instance=data, schema=self.schema)
            return True, ""
        except ValidationError as e:
            return False, e.message

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行结构校验逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含校验结果
        """
        data_list = context.get(self.data_key, [])

        # 如果是单个对象而不是列表，包装成列表
        if isinstance(data_list, dict):
            data_list = [data_list]

        if not data_list:
            raise ValueError(f"No data found in context for key: {self.data_key}")

        valid_data: List[Dict] = []
        invalid_data: List[Dict] = []

        for data in data_list:
            is_valid, error = self._validate_data(data)
            if is_valid:
                valid_data.append(data)
            else:
                invalid_data.append({
                    self.id_field: data.get(self.id_field, "unknown"),
                    "error": error,
                    "data": data
                })

        # 存储校验结果
        context.set(self.valid_key, valid_data)
        context.set(self.invalid_key, invalid_data)
        context.set(self.summary_key, {
            "total": len(data_list),
            "valid": len(valid_data),
            "invalid": len(invalid_data)
        })

        return context
