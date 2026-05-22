"""LLM 客户端工厂模块
提供 VolcanoLLM 的单例/工厂函数，统一配置管理。
"""

from functools import lru_cache
from backend.providers import VolcanoLLM
from backend.app.core.config import settings


@lru_cache()
def get_llm() -> VolcanoLLM:
    """获取 LLM 客户端单例"""
    return VolcanoLLM(
        key=settings.DOUBAO_SEED_API_KEY,
        model_name=settings.DOUBAO_SEED,
    )
