"""
⚠️  警告：此模块已弃用！
剧本生成服务已迁移到 backend.v1.app.script.service.script_generation_service
请更新导入路径，此文件将在后续版本中删除。
"""
import warnings
warnings.warn(
    "backend.v1.app.generate.service.stages.script 已弃用，请使用 backend.v1.app.script.service.script_generation_service",
    DeprecationWarning,
    stacklevel=2
)

# 从新模块导入，保持兼容
from backend.v1.app.script.service.script_generation_service import (
    ScriptGenerationService,
    script_generation_service,
    SCENE_TYPE_MAP
)

__all__ = [
    "ScriptGenerationService",
    "script_generation_service",
    "SCENE_TYPE_MAP"
]
