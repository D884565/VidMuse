from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import FACTOR_INDEX, STRATEGY_LIBRARY, INSPIRATION_TEMPLATES
from backend.v1.app.models.inspiration_template import Factor, Strategy, InspirationTemplate
from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO, TemplateFactorRelationDAO
)
from backend.store.database.async_database import get_db
import logging

logger = logging.getLogger(__name__)


class TemplatePersistenceProcessor(BaseProcessor):
    """
    模板持久化处理器
    将流水线生成的因子、策略、模板批量持久化到数据库
    """

    async def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取因子索引、策略库和模板列表
        2. 批量保存因子（去重）
        3. 批量保存策略（去重）
        4. 批量保存模板及关联关系
        5. 将保存后的ID信息更新到上下文
        """
        factor_index: Dict[str, Factor] = context.get(FACTOR_INDEX, {})
        strategy_library: Dict[str, Strategy] = context.get(STRATEGY_LIBRARY, {})
        templates: List[InspirationTemplate] = context.get(INSPIRATION_TEMPLATES, [])

        if not templates:
            logger.warning("没有模板需要持久化")
            return context

        logger.info(f"开始持久化灵感模板，数量: {len(templates)}")

        # 获取数据库会话（正确使用异步生成器）
        db_gen = get_db()
        db = await anext(db_gen)

        try:
            # 1. 保存所有因子
            saved_factors = {}
            for factor_id, factor in factor_index.items():
                try:
                    # 检查因子是否已存在
                    existing = await FactorDAO.get_factor_by_factor_id(db, factor_id)
                    if existing:
                        logger.info(f"因子 {factor_id} 已存在，跳过创建")
                        saved_factors[factor_id] = existing
                        continue

                    # 创建新因子
                    factor_data = {
                        "factor_id": factor.factor_id,
                        "factor_type": factor.factor_type,
                        "name": factor.name,
                        "description": factor.description,
                        "applicable_scenarios": factor.applicable_scenarios,
                        "data_schema": factor.data_schema,
                        "example": factor.example,
                        "tags": factor.tags,
                        "popularity": factor.popularity,
                        "usage_count": factor.usage_count
                    }
                    saved_factor = await FactorDAO.create_factor(db, factor_data)
                    saved_factors[factor_id] = saved_factor
                    logger.info(f"成功保存因子: {factor_id} - {factor.name}")
                except Exception as e:
                    logger.error(f"保存因子 {factor_id} 失败: {str(e)}", exc_info=True)
                    continue

            # 2. 保存所有策略
            saved_strategies = {}
            for strategy_id, strategy in strategy_library.items():
                try:
                    # 检查策略是否已存在
                    existing = await StrategyDAO.get_strategy_by_strategy_id(db, strategy_id)
                    if existing:
                        logger.info(f"策略 {strategy_id} 已存在，跳过创建")
                        saved_strategies[strategy_id] = existing
                        continue

                    # 创建新策略
                    strategy_data = {
                        "strategy_id": strategy.strategy_id,
                        "name": strategy.name,
                        "description": strategy.description,
                        "applicable_scenarios": strategy.applicable_scenarios,
                        "core_logic": strategy.core_logic,
                        "required_factor_types": strategy.required_factor_types,
                        "optional_factor_types": strategy.optional_factor_types,
                        "combination_rules": strategy.combination_rules,
                        "success_rate": strategy.success_rate,
                        "tags": strategy.tags,
                        "usage_count": strategy.usage_count
                    }
                    saved_strategy = await StrategyDAO.create_strategy(db, strategy_data)
                    saved_strategies[strategy_id] = saved_strategy
                    logger.info(f"成功保存策略: {strategy_id} - {strategy.name}")
                except Exception as e:
                    logger.error(f"保存策略 {strategy_id} 失败: {str(e)}", exc_info=True)
                    continue

            # 3. 保存所有模板
            saved_templates = []
            for template in templates:
                try:
                    # 检查模板是否已存在
                    existing = await InspirationTemplateDAO.get_template_by_template_id(db, template.template_id)
                    if existing:
                        logger.info(f"模板 {template.template_id} 已存在，跳过创建")
                        # 转换为字典
                        existing_dict = {
                            "id": existing.id,
                            "template_id": existing.template_id,
                            "strategy_id": existing.strategy_id,
                            "name": existing.name,
                            "description": existing.description,
                            "combination_example": existing.combination_example,
                            "version": existing.version,
                            "success_rate": float(existing.success_rate) if existing.success_rate is not None else 0.0,
                            "usage_count": existing.usage_count,
                            "created_at": existing.created_at.isoformat() if existing.created_at else "",
                            "updated_at": existing.updated_at.isoformat() if existing.updated_at else "",
                        }
                        saved_templates.append(existing_dict)
                        continue

                    # 准备关联因子数据
                    factor_relations = []

                    # 添加必填因子
                    for idx, factor in enumerate(template.required_factors):
                        factor_relations.append({
                            "factor_id": factor.factor_id,
                            "factor_usage_type": 1,  # 1=必填
                            "sort_order": idx
                        })

                    # 添加可选因子
                    for idx, factor in enumerate(template.optional_factors):
                        factor_relations.append({
                            "factor_id": factor.factor_id,
                            "factor_usage_type": 2,  # 2=可选
                            "sort_order": len(template.required_factors) + idx
                        })

                    # 创建模板数据
                    template_data = {
                        "template_id": template.template_id,
                        "strategy_id": template.strategy_id,
                        "name": template.name,
                        "description": template.description,
                        "combination_example": template.combination_example,
                        "version": template.version,
                        "success_rate": template.success_rate,
                        "usage_count": template.usage_count
                    }

                    # 创建模板
                    saved_template = await InspirationTemplateDAO.create_template(db, template_data)

                    # 创建关联因子
                    if factor_relations:
                        relations_data = []
                        for rel in factor_relations:
                            # 检查因子是否存在
                            factor = await FactorDAO.get_factor_by_factor_id(db, rel["factor_id"])
                            if not factor:
                                logger.warning(f"因子 {rel['factor_id']} 不存在，跳过关联")
                                continue

                            relations_data.append({
                                "template_id": saved_template.template_id,
                                "factor_id": rel["factor_id"],
                                "factor_usage_type": rel["factor_usage_type"],
                                "sort_order": rel.get("sort_order", 0)
                            })

                        if relations_data:
                            await TemplateFactorRelationDAO.batch_create_relations(db, relations_data)

                    # 转换为字典格式返回
                    saved_template_dict = {
                        "id": saved_template.id,
                        "template_id": saved_template.template_id,
                        "strategy_id": saved_template.strategy_id,
                        "name": saved_template.name,
                        "description": saved_template.description,
                        "combination_example": saved_template.combination_example,
                        "version": saved_template.version,
                        "success_rate": float(saved_template.success_rate) if saved_template.success_rate is not None else 0.0,
                        "usage_count": saved_template.usage_count,
                        "created_at": saved_template.created_at.isoformat() if saved_template.created_at else "",
                        "updated_at": saved_template.updated_at.isoformat() if saved_template.updated_at else "",
                    }

                    saved_templates.append(saved_template_dict)
                    logger.info(f"成功保存模板: {template.template_id} - {template.name}")
                except Exception as e:
                    logger.error(f"保存模板 {template.template_id} 失败: {str(e)}", exc_info=True)
                    continue

            logger.info(f"持久化完成: 保存因子 {len(saved_factors)} 个，策略 {len(saved_strategies)} 个，模板 {len(saved_templates)} 个")

            # 更新上下文，保存持久化后的结果
            context.set("SAVED_FACTORS", saved_factors)
            context.set("SAVED_STRATEGIES", saved_strategies)
            context.set("SAVED_TEMPLATES", saved_templates)

            return context

        finally:
            # 关闭生成器，触发自动关闭会话
            try:
                await anext(db_gen)
            except StopAsyncIteration:
                pass
