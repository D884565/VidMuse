"""基于灵感模板的剧本生成服务

职责：处理与灵感模板相关的剧本生成逻辑，包括模板加载、参数处理、提示词构建等
与剧本生成主服务解耦，保持单一职责
"""
import json
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script

logger = logging.getLogger(__name__)


class TemplateScriptService:
    """基于灵感模板的剧本生成服务"""

    @staticmethod
    async def increment_template_usage(db: AsyncSession, template_id: str) -> None:
        """增加模板使用次数

        :param db: 数据库会话
        :param template_id: 模板ID
        """
        from backend.v1.app.models.inspiration_template import InspirationTemplate
        from sqlalchemy import update

        stmt = (
            update(InspirationTemplate)
            .where(InspirationTemplate.template_id == template_id)
            .values(usage_count=InspirationTemplate.usage_count + 1)
        )
        await db.execute(stmt)

    @staticmethod
    async def get_template(db: AsyncSession, template_id: str) -> Optional[Dict[str, Any]]:
        """获取模板详情

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 模板信息字典，不存在时返回None
        """
        from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import InspirationTemplateDAO
        try:
            template = InspirationTemplateDAO.get_template_by_template_id(db.sync_session, template_id)
            if template:
                return {
                    "template_id": template.template_id,
                    "strategy_id": template.strategy_id,
                    "name": template.name,
                    "description": template.description,
                    "combination_example": template.combination_example,
                    "version": template.version,
                    "success_rate": float(template.success_rate) if template.success_rate is not None else 0.0,
                }
            return None
        except Exception as e:
            logger.warning(f"获取模板信息失败: {str(e)}")
            return None

    @staticmethod
    async def get_strategy(db: AsyncSession, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取策略详情

        :param db: 数据库会话
        :param strategy_id: 策略ID
        :return: 策略信息字典，不存在时返回None
        """
        from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import StrategyDAO
        try:
            strategy = StrategyDAO.get_strategy_by_strategy_id(db.sync_session, strategy_id)
            if strategy:
                return {
                    "strategy_id": strategy.strategy_id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "core_logic": strategy.core_logic,
                    "required_factor_types": strategy.required_factor_types,
                    "optional_factor_types": strategy.optional_factor_types,
                    "combination_rules": strategy.combination_rules,
                }
            return None
        except Exception as e:
            logger.warning(f"获取策略信息失败: {str(e)}")
            return None

    @staticmethod
    async def get_template_factors(db: AsyncSession, template_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取模板关联的因子列表

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 因子列表，不存在时返回None
        """
        from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import TemplateFactorRelationDAO, FactorDAO
        try:
            relations = TemplateFactorRelationDAO.get_relations_by_template_id(db.sync_session, template_id)
            factors = []
            for rel in relations:
                factor = FactorDAO.get_factor_by_factor_id(db.sync_session, rel.factor_id)
                if factor:
                    factors.append({
                        "factor_id": factor.factor_id,
                        "factor_type": factor.factor_type,
                        "name": factor.name,
                        "description": factor.description,
                        "data_schema": factor.data_schema,
                        "factor_usage_type": rel.factor_usage_type,
                        "sort_order": rel.sort_order,
                    })
            return factors
        except Exception as e:
            logger.warning(f"获取模板因子失败: {str(e)}")
            return None

    @staticmethod
    def build_prompt_with_template(
        base_prompt: str,
        template: Dict[str, Any],
        template_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """基于模板构建生成提示词

        :param base_prompt: 基础提示词
        :param template: 模板信息
        :param template_params: 用户自定义模板参数
        :return: 合并后的完整提示词
        """
        # 添加模板相关信息
        template_section = [
            "## 创作模板参考",
            f"模板名称：{template.get('name', '')}",
            f"模板描述：{template.get('description', '')}",
        ]

        if template.get('core_logic'):
            template_section.append(f"创作逻辑：{template.get('core_logic')}")

        if template.get('combination_rules'):
            template_section.append(f"组合规则：{template.get('combination_rules')}")

        if template_params:
            template_section.append("\n## 用户自定义模板参数")
            for key, value in template_params.items():
                template_section.append(f"- {key}: {value}")

        if template.get('combination_example'):
            template_section.append("\n## 模板示例参考")
            template_section.append(json.dumps(template.get('combination_example'), ensure_ascii=False, indent=2))

        # 合并prompt
        template_text = "\n".join(template_section)
        return f"{base_prompt}\n\n{template_text}\n\n请基于以上模板和参数生成符合要求的剧本。"

    @staticmethod
    async def process_template_data(
        db: AsyncSession,
        template_id: str,
        template_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理模板相关数据，加载模板、策略和因子信息

        :param db: 数据库会话
        :param template_id: 模板ID
        :param template_params: 用户自定义模板参数
        :return: 处理后的模板相关数据字典
        """
        result = {
            "template": None,
            "strategy": None,
            "used_factors": None,
            "prompt": None
        }

        template = await TemplateScriptService.get_template(db, template_id)
        if not template:
            logger.warning(f"模板ID {template_id} 不存在")
            return result

        result["template"] = template
        strategy_id = template.get('strategy_id')

        if strategy_id:
            strategy = await TemplateScriptService.get_strategy(db, strategy_id)
            result["strategy"] = strategy

        used_factors = await TemplateScriptService.get_template_factors(db, template_id)
        result["used_factors"] = used_factors

        return result


# 模块级单例
template_script_service = TemplateScriptService()
