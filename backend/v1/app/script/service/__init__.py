"""剧本模块服务层"""
from backend.v1.app.script.service.script_generation_service import script_generation_service, ScriptGenerationService
from backend.v1.app.script.service.template_script_service import template_script_service, TemplateScriptService
from backend.v1.app.script.service.inspiration_template_query_service import inspiration_template_query_service, InspirationTemplateQueryService

__all__ = [
    "script_generation_service",
    "ScriptGenerationService",
    "template_script_service",
    "TemplateScriptService",
    "inspiration_template_query_service",
    "InspirationTemplateQueryService",
]
