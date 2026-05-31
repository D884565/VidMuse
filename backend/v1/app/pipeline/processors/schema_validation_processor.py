import os
from typing import Dict, List, Tuple, Optional
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.pipeline.utils.template_validator import (
    load_json_file,
    validate_with_schema,
    load_template,
    VALID_TEMPLATE_DIR
)


class SchemaValidationProcessor(BaseProcessor):
    """
    通用结构校验处理器
    使用JSON Schema校验数据结构是否符合要求，支持切片、商品、视频等多种类型的数据校验
    """

    def __init__(self, schema_path: str = None,
                 template_type: str = None,
                 data_key: str = "slice_data",
                 valid_key: str = "valid_slices",
                 invalid_key: str = "invalid_slices",
                 summary_key: str = "validation_summary",
                 id_field: str = "slice_id"):
        """
        初始化结构校验处理器

        :param schema_path: JSON Schema文件路径，优先级高于template_type
        :param template_type: 模板类型，可选值：video, slice, product，与schema_path二选一
        :param data_key: 从上下文中获取待校验数据的键名
        :param valid_key: 校验通过数据存储的键名
        :param invalid_key: 校验失败数据存储的键名
        :param summary_key: 校验汇总信息存储的键名
        :param id_field: 数据中唯一标识的字段名，用于错误信息展示
        """
        # 加载Schema：优先使用schema_path，其次使用template_type，默认使用slice模板
        if schema_path is not None:
            # 使用指定路径加载Schema，自动验证有效性并缓存
            self.schema = load_json_file(schema_path, validate_schema=True)
        elif template_type is not None:
            # 按模板类型加载
            self.schema = load_template(template_type)
        else:
            # 默认使用slice模板
            self.schema = load_template("slice")
        self.data_key = data_key
        self.valid_key = valid_key
        self.invalid_key = invalid_key
        self.summary_key = summary_key
        self.id_field = id_field

    def _validate_data(self, data: Dict) -> Tuple[bool, str]:
        """
        校验单个数据是否符合Schema要求

        :param data: 待校验的数据
        :return: (是否通过校验, 错误信息)
        """
        # 使用通用校验方法，支持更详细的错误信息
        return validate_with_schema(data, self.schema)

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

    @classmethod
    def for_slice(cls, **kwargs) -> "SchemaValidationProcessor":
        """
        创建切片数据校验处理器
        """
        return cls(template_type="slice", **kwargs)

    @classmethod
    def for_video(cls, **kwargs) -> "SchemaValidationProcessor":
        """
        创建视频数据校验处理器
        """
        config = {
            "template_type": "video",
            "data_key": "video_data",
            "valid_key": "valid_videos",
            "invalid_key": "invalid_videos"
        }
        config.update(kwargs)
        return cls(**config)

    @classmethod
    def for_product(cls, **kwargs) -> "SchemaValidationProcessor":
        """
        创建商品数据校验处理器
        """
        return cls(template_type="product", data_key="product_data",
                   valid_key="valid_products", invalid_key="invalid_products",
                   id_field="product_id", **kwargs)
