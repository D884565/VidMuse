from typing import Dict, Any, Optional
import json
from .template_validator import load_prompt, load_template, get_supported_prompt_types, get_supported_template_types


class PromptManager:
    """
    提示词管理类
    统一管理所有提示词和模板的加载、格式化和缓存
    提供类型安全的访问接口，避免硬编码和重复代码
    """

    # 提示词类型常量
    SLICE_UNDERSTANDING = "slice_understanding"
    VIDEO_OVERALL_UNDERSTANDING = "video_overall_understanding"
    PRODUCT_UNDERSTANDING = "product_understanding"

    # 模板类型常量
    TEMPLATE_SLICE = "slice"
    TEMPLATE_VIDEO = "video"
    TEMPLATE_PRODUCT = "product"

    # 输出结构字段常量（与JSON模板结构对应）
    FIELD_SLICE_TEMPLATE = "片段模板"
    FIELD_TEMPLATE_NAME = "模板名称"
    FIELD_TEMPLATE_TYPE = "模板类型"
    FIELD_CREATIVE_ELEMENTS = "创作要素"
    FIELD_SCRIPT = "台词"
    FIELD_SCREEN = "画面"
    FIELD_ACTION = "动作"
    FIELD_CAMERA_MOVE = "运镜"
    FIELD_DURATION = "时长"
    FIELD_EMOTION_SCORE = "情绪评分"
    FIELD_GENERATE_PROMPT = "生成Prompt完整模板"
    FIELD_VIDEO_BASIC_INFO = "视频基本信息"
    FIELD_SEGMENT_RELATIONS = "片段间关系"

    # 单例实例
    _instance: Optional['PromptManager'] = None

    def __new__(cls) -> 'PromptManager':
        """单例模式，避免重复加载缓存"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._prompt_cache: Dict[str, Dict[str, Any]] = {}
            cls._instance._template_cache: Dict[str, Dict[str, Any]] = {}
        return cls._instance

    def get_prompt(self, prompt_type: str, **kwargs) -> str:
        """
        获取格式化后的提示词

        Args:
            prompt_type: 提示词类型，使用类常量
            **kwargs: 格式化参数，替换提示词中的占位符
                - output_schema: 要注入的JSON Schema字符串（可选）

        Returns:
            格式化后的提示词字符串
        """
        if prompt_type not in get_supported_prompt_types():
            raise ValueError(f"不支持的提示词类型: {prompt_type}")

        # 从缓存或加载提示词文本
        if prompt_type not in self._prompt_cache:
            self._prompt_cache[prompt_type] = load_prompt(prompt_type)

        template = self._prompt_cache[prompt_type]

        # 格式化提示词，注入模板
        if kwargs:
            try:
                # 如果有output_schema参数，序列化为JSON字符串
                if 'output_schema' in kwargs and isinstance(kwargs['output_schema'], dict):
                    kwargs['output_schema'] = json.dumps(kwargs['output_schema'], ensure_ascii=False, indent=2)
                return template.format(**kwargs)
            except KeyError as e:
                raise ValueError(f"提示词缺少必要的格式化参数: {e}")

        return template

    def get_template(self, template_type: str) -> Dict[str, Any]:
        """
        获取JSON校验模板

        Args:
            template_type: 模板类型，使用类常量

        Returns:
            模板字典
        """
        if template_type not in get_supported_template_types():
            raise ValueError(f"不支持的模板类型: {template_type}")

        # 从缓存或加载模板
        if template_type not in self._template_cache:
            self._template_cache[template_type] = load_template(template_type)

        return self._template_cache[template_type]

    def get_slice_understanding_prompt(self) -> str:
        """获取分片理解提示词（快捷方法，自动注入slice模板）"""
        return self.get_prompt(
            self.SLICE_UNDERSTANDING,
            output_schema=self.get_slice_template()
        )

    def get_video_overall_understanding_prompt(self) -> str:
        """获取视频整体理解提示词（快捷方法，自动注入video模板）"""
        return self.get_prompt(
            self.VIDEO_OVERALL_UNDERSTANDING,
            output_schema=self.get_video_template()
        )

    def get_product_understanding_prompt(self) -> str:
        """获取商品理解提示词（快捷方法，自动注入product模板）"""
        return self.get_prompt(
            self.PRODUCT_UNDERSTANDING,
            output_schema=self.get_product_template()
        )

    def get_slice_template(self) -> Dict[str, Any]:
        """获取分片校验模板（快捷方法）"""
        return self.get_template(self.TEMPLATE_SLICE)

    def get_video_template(self) -> Dict[str, Any]:
        """获取视频整体校验模板（快捷方法）"""
        return self.get_template(self.TEMPLATE_VIDEO)

    def get_product_template(self) -> Dict[str, Any]:
        """获取商品校验模板（快捷方法）"""
        return self.get_template(self.TEMPLATE_PRODUCT)


# 全局实例
prompt_manager = PromptManager()
