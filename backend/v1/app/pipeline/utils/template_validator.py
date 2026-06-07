import json
import os
from typing import Dict, Any, Optional, Tuple
import jsonschema
from jsonschema import Draft7Validator

# 模板类型与对应模板文件的映射
TEMPLATE_TYPE_MAP = {
    "video": "video_valid.json",
    "slice": "slice_valid.json",
    "product": "product_valid.json",
    "factor": "factor_schema.json",
    "strategy": "strategy_schema.json"
}

# 模板文件根目录（相对于当前文件的路径）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 向上导航到项目根目录，然后定位到模板目录
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../../../"))
VALID_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "resources", "template", "resolve", "valid_template")
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "resources", "template", "resolve")
PROMPT_DIR = os.path.join(PROJECT_ROOT, "resources", "template", "resolve", "prompts")

# 缓存已加载的模板，避免重复读取文件
_template_cache: Dict[str, Dict[str, Any]] = {}
# 通用JSON文件缓存
_general_json_cache: Dict[str, Any] = {}
# 提示词类型与对应文件的映射
PROMPT_TYPE_MAP = {
    "slice_understanding": "slice_understanding.txt",
    "video_overall_understanding": "video_overall_understanding.txt",
    "product_understanding": "product_understanding.txt",
    "direct_video_understanding": "direct_video_understanding.txt",
    "extract_common_factors": "extract_common_factors.txt",
    "generate_strategy": "generate_strategy.txt",
    "extract_video_common_features": "extract_video_common_features.txt",
    "script_system": "script_system.txt",
    "script_generation": "script_generation.txt",
    "script_user_intent": "script_user_intent.txt",
    "script_supplement": "script_supplement.txt",
    "script_product_info": "script_product_info.txt",
    "script_reference_images": "script_reference_images.txt",
    "script_rag_header": "script_rag_header.txt",
}
# 提示词缓存
_prompt_cache: Dict[str, Dict[str, Any]] = {}


def load_json_file(file_path: str,
                  validate_schema: bool = False,
                  encoding: str = "utf-8",
                  use_cache: bool = True) -> Any:
    """
    通用JSON文件加载方法

    Args:
        file_path: JSON文件路径
        validate_schema: 是否验证文件内容是有效的JSON Schema
        encoding: 文件编码，默认utf-8
        use_cache: 是否使用缓存，默认True

    Returns:
        解析后的JSON数据

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON解析错误或Schema验证失败
        RuntimeError: 加载过程中发生其他错误
    """
    # 转换为绝对路径
    abs_path = os.path.abspath(file_path)

    # 检查缓存
    if use_cache and abs_path in _general_json_cache:
        return _general_json_cache[abs_path]

    # 检查文件是否存在
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"文件不存在: {abs_path}")

    # 读取并解析JSON文件
    try:
        with open(abs_path, "r", encoding=encoding) as f:
            data = json.load(f)

        # 如果需要验证是有效的JSON Schema
        if validate_schema:
            Draft7Validator.check_schema(data)

        # 存入缓存
        if use_cache:
            _general_json_cache[abs_path] = data

        return data

    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析错误: {abs_path}, 错误: {str(e)}")
    except jsonschema.SchemaError as e:
        raise ValueError(f"不是有效的JSON Schema: {abs_path}, 错误: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"加载文件失败: {abs_path}, 错误: {str(e)}")


def load_template(template_type: str) -> Dict[str, Any]:
    """
    加载指定类型的JSON校验模板

    Args:
        template_type: 模板类型，可选值：video, slice, product

    Returns:
        加载成功返回模板字典

    Raises:
        ValueError: 不支持的模板类型
        FileNotFoundError: 模板文件不存在
        其他异常参考load_json_file函数
    """
    # 检查模板类型是否支持
    if template_type not in TEMPLATE_TYPE_MAP:
        raise ValueError(f"不支持的模板类型: {template_type}，支持的类型: {list(TEMPLATE_TYPE_MAP.keys())}")

    # 检查缓存中是否已有该模板
    if template_type in _template_cache:
        return _template_cache[template_type]

    # 构造模板文件路径
    template_file = os.path.join(VALID_TEMPLATE_DIR, TEMPLATE_TYPE_MAP[template_type])

    # 使用通用加载函数加载并验证Schema
    template = load_json_file(template_file, validate_schema=True)

    # 存入缓存
    _template_cache[template_type] = template
    return template


def validate_with_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, str]:
    """
    通用JSON校验方法，使用指定的JSON Schema校验数据

    Args:
        data: 要校验的数据字典
        schema: JSON Schema模板

    Returns:
        (校验是否通过, 错误信息)，校验通过时错误信息为空字符串
    """
    try:
        # 验证Schema本身是否有效
        Draft7Validator.check_schema(schema)

        # 执行校验
        validator = Draft7Validator(schema)
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

        # 使用通用校验方法
        return validate_with_schema(data, template)

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


def load_prompt(prompt_type: str) -> str:
    """
    加载指定类型的提示词模板

    Args:
        prompt_type: 提示词类型，可选值：slice_understanding, video_overall_understanding, product_understanding

    Returns:
        加载成功返回提示词文本内容，包含占位符

    Raises:
        ValueError: 不支持的提示词类型
        FileNotFoundError: 提示词文件不存在
    """
    if prompt_type not in PROMPT_TYPE_MAP:
        raise ValueError(f"不支持的提示词类型: {prompt_type}，支持的类型: {list(PROMPT_TYPE_MAP.keys())}")

    if prompt_type in _prompt_cache:
        return _prompt_cache[prompt_type]

    prompt_file = os.path.join(PROMPT_DIR, PROMPT_TYPE_MAP[prompt_type])

    # 读取TXT格式的提示词文件
    abs_path = os.path.abspath(prompt_file)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"提示词文件不存在: {abs_path}")

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()
    except Exception as e:
        raise RuntimeError(f"加载提示词文件失败: {abs_path}, 错误: {str(e)}")

    _prompt_cache[prompt_type] = prompt_content
    return prompt_content


def get_supported_prompt_types() -> list[str]:
    """
    获取支持的提示词类型列表
    """
    return list(PROMPT_TYPE_MAP.keys())