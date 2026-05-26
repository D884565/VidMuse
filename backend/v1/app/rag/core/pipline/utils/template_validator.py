import json
import os
from typing import Dict, Any, Optional, Tuple
import jsonschema
from jsonschema import Draft7Validator

# 模板类型与对应模板文件的映射
TEMPLATE_TYPE_MAP = {
    "video": "video_valid.json",
    "slice": "slice_valid.json",
    "product": "product_valid.json"
}

# 模板文件根目录
file_path = "E:/project/py/byte/VidMuse/resources/template/resolve/valid_template/"

# 缓存已加载的模板，避免重复读取文件
_template_cache: Dict[str, Dict[str, Any]] = {}


def load_template(template_type: str) -> Optional[Dict[str, Any]]:
    """
    加载指定类型的JSON校验模板

    Args:
        template_type: 模板类型，可选值：video, slice, product

    Returns:
        加载成功返回模板字典，失败返回None
    """
    # 检查模板类型是否支持
    if template_type not in TEMPLATE_TYPE_MAP:
        raise ValueError(f"不支持的模板类型: {template_type}，支持的类型: {list(TEMPLATE_TYPE_MAP.keys())}")

    # 检查缓存中是否已有该模板
    if template_type in _template_cache:
        return _template_cache[template_type]

    # 构造模板文件路径
    template_file = file_path + TEMPLATE_TYPE_MAP[template_type]

    # 检查文件是否存在
    if not os.path.exists(template_file):
        raise FileNotFoundError(f"模板文件不存在: {template_file}")

    # 读取并解析JSON文件
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            template = json.load(f)

        # 验证模板本身是否是有效的JSON Schema
        Draft7Validator.check_schema(template)

        # 存入缓存
        _template_cache[template_type] = template
        return template

    except json.JSONDecodeError as e:
        raise ValueError(f"模板文件JSON解析错误: {template_file}, 错误: {str(e)}")
    except jsonschema.SchemaError as e:
        raise ValueError(f"模板不是有效的JSON Schema: {template_file}, 错误: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"加载模板文件失败: {template_file}, 错误: {str(e)}")


def validate_data(data: Dict[str, Any], template_type: str) -> Tuple[bool, str]:
    """
    使用指定类型的模板校验数据

    Args:
        data: 要校验的数据字典
        template_type: 模板类型，可选值：video, slice, product

    Returns:
        (校验是否通过, 错误信息)，校验通过时错误信息为空字符串
    """
    try:
        # 加载模板
        template = load_template(template_type)
        if not template:
            return False, "模板加载失败"

        # 执行校验
        validator = Draft7Validator(template)
        errors = list(validator.iter_errors(data))

        if not errors:
            return True, ""

        # 格式化错误信息
        error_messages = []
        for idx, error in enumerate(errors, 1):
            path = ".".join(str(p) for p in error.path) if error.path else "根节点"
            error_messages.append(f"错误 {idx}: 路径[{path}] - {error.message}")

        return False, "\n".join(error_messages)

    except Exception as e:
        return False, f"校验过程发生错误: {str(e)}"


def validate_json_string(json_str: str, template_type: str) -> Tuple[bool, str]:
    """
    校验JSON字符串格式是否符合指定模板

    Args:
        json_str: 要校验的JSON字符串
        template_type: 模板类型，可选值：video, slice, product

    Returns:
        (校验是否通过, 错误信息)，校验通过时错误信息为空字符串
    """
    try:
        data = json.loads(json_str)
        return validate_data(data, template_type)
    except json.JSONDecodeError as e:
        return False, f"JSON解析错误: {str(e)}"


def get_supported_template_types() -> list[str]:
    """
    获取支持的模板类型列表
    """
    return list(TEMPLATE_TYPE_MAP.keys())