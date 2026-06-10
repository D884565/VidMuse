# 兼容旧导入，已迁移到script模块
# 延迟导入避免循环依赖
def __getattr__(name):
    if name in [
        "template_script_service",
        "TemplateScriptService",
        "script_generation_service",
        "ScriptGenerationService"
    ]:
        from backend.v1.app.script.service import (
            template_script_service,
            TemplateScriptService,
            script_generation_service,
            ScriptGenerationService
        )
        return locals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "template_script_service",
    "TemplateScriptService",
    "script_generation_service",
    "ScriptGenerationService",
]
