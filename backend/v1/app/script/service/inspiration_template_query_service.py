"""灵感模板查询服务

职责：提供给用户的灵感模板查询功能，包括模板列表查询、详情查询、热门推荐等
仅提供查询功能，不包含修改操作
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.script.dao.inspiration_template_dao import script_inspiration_template_dao

logger = logging.getLogger(__name__)


class InspirationTemplateQueryService:
    """灵感模板查询服务"""

    @staticmethod
    async def get_template_detail(
        db: AsyncSession,
        template_id: str,
        include_strategy: bool = True,
        include_factors: bool = True
    ) -> Optional[Dict[str, Any]]:
        """获取模板详情
        :param db: 数据库会话
        :param template_id: 模板ID
        :param include_strategy: 是否包含关联的策略信息
        :param include_factors: 是否包含关联的因子信息
        :return: 模板详情字典，不存在时返回None
        """
        try:
            # 获取模板基本信息
            template = await script_inspiration_template_dao.get_template_by_template_id(db, template_id)
            if not template:
                logger.warning(f"模板ID {template_id} 不存在")
                return None

            # 构建返回数据
            result = {
                "template_id": template.template_id,
                "strategy_id": template.strategy_id,
                "name": template.name,
                "description": template.description,
                "combination_example": template.combination_example,
                "version": template.version,
                "success_rate": float(template.success_rate) if template.success_rate is not None else 0.0,
                "usage_count": template.usage_count,
                "created_at": template.created_at.isoformat() if template.created_at else None,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None
            }

            # 加载关联的策略信息
            if include_strategy and template.strategy_id:
                strategy = await script_inspiration_template_dao.get_strategy_by_strategy_id(db, template.strategy_id)
                if strategy:
                    result["strategy"] = {
                        "strategy_id": strategy.strategy_id,
                        "name": strategy.name,
                        "description": strategy.description,
                        "applicable_scenarios": strategy.applicable_scenarios,
                        "core_logic": strategy.core_logic,
                        "required_factor_types": strategy.required_factor_types,
                        "optional_factor_types": strategy.optional_factor_types,
                        "combination_rules": strategy.combination_rules,
                        "success_rate": float(strategy.success_rate) if strategy.success_rate is not None else 0.0,
                        "tags": strategy.tags,
                        "usage_count": strategy.usage_count
                    }

            # 加载关联的因子信息
            if include_factors:
                factors = await script_inspiration_template_dao.get_template_factors(db, template_id)
                result["factors"] = factors

            return result

        except Exception as e:
            logger.error(f"获取模板详情失败: {str(e)}", exc_info=True)
            return None

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        strategy_id: Optional[str] = None,
        keyword: Optional[str] = None,
        version: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
        include_basic_info: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """分页查询模板列表
        :param db: 数据库会话
        :param strategy_id: 按关联策略ID筛选（可选）
        :param keyword: 按名称/描述模糊搜索（可选）
        :param version: 按版本号筛选（可选）
        :param min_success_rate: 最低成功率筛选（可选）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :param include_basic_info: 是否包含基础额外信息（策略名称、因子数量等）
        :return: (总数量, 模板列表)
        """
        try:
            total, templates = await script_inspiration_template_dao.list_templates(
                db=db,
                strategy_id=strategy_id,
                keyword=keyword,
                version=version,
                min_success_rate=min_success_rate,
                page=page,
                page_size=page_size
            )

            result_list = []
            for template in templates:
                item = {
                    "template_id": template.template_id,
                    "strategy_id": template.strategy_id,
                    "name": template.name,
                    "description": template.description,
                    "version": template.version,
                    "success_rate": float(template.success_rate) if template.success_rate is not None else 0.0,
                    "usage_count": template.usage_count,
                    "created_at": template.created_at.isoformat() if template.created_at else None
                }

                # 如果需要基础信息，补充策略名称和因子数量
                if include_basic_info:
                    # 获取策略名称
                    if template.strategy_id:
                        strategy = await script_inspiration_template_dao.get_strategy_by_strategy_id(db, template.strategy_id)
                        if strategy:
                            item["strategy_name"] = strategy.name

                    # 获取因子数量
                    factors = await script_inspiration_template_dao.get_template_factors(db, template.template_id)
                    item["factor_count"] = len(factors)

                result_list.append(item)

            return total, result_list

        except Exception as e:
            logger.error(f"查询模板列表失败: {str(e)}", exc_info=True)
            return 0, []

    @staticmethod
    async def get_strategy_detail(
        db: AsyncSession,
        strategy_id: str,
        include_templates: bool = False,
        template_limit: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取策略详情
        :param db: 数据库会话
        :param strategy_id: 策略ID
        :param include_templates: 是否包含该策略下的模板列表
        :param template_limit: 包含模板时的返回数量限制
        :return: 策略详情字典，不存在时返回None
        """
        try:
            strategy = await script_inspiration_template_dao.get_strategy_by_strategy_id(db, strategy_id)
            if not strategy:
                logger.warning(f"策略ID {strategy_id} 不存在")
                return None

            result = {
                "strategy_id": strategy.strategy_id,
                "name": strategy.name,
                "description": strategy.description,
                "applicable_scenarios": strategy.applicable_scenarios,
                "core_logic": strategy.core_logic,
                "required_factor_types": strategy.required_factor_types,
                "optional_factor_types": strategy.optional_factor_types,
                "combination_rules": strategy.combination_rules,
                "success_rate": float(strategy.success_rate) if strategy.success_rate is not None else 0.0,
                "tags": strategy.tags,
                "usage_count": strategy.usage_count,
                "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
                "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None
            }

            # 包含关联的模板列表
            if include_templates:
                _, templates = await script_inspiration_template_dao.list_templates(
                    db=db,
                    strategy_id=strategy_id,
                    page=1,
                    page_size=template_limit
                )
                result["templates"] = [
                    {
                        "template_id": t.template_id,
                        "name": t.name,
                        "success_rate": float(t.success_rate) if t.success_rate is not None else 0.0,
                        "usage_count": t.usage_count
                    } for t in templates
                ]

            return result

        except Exception as e:
            logger.error(f"获取策略详情失败: {str(e)}", exc_info=True)
            return None

    @staticmethod
    async def list_strategies(
        db: AsyncSession,
        applicable_scenario: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """分页查询策略列表
        :param db: 数据库会话
        :param applicable_scenario: 按适用场景筛选（可选）
        :param keyword: 按名称/描述模糊搜索（可选）
        :param tag: 按标签筛选（可选）
        :param min_success_rate: 最低成功率筛选（可选）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: (总数量, 策略列表)
        """
        try:
            total, strategies = await script_inspiration_template_dao.list_strategies(
                db=db,
                applicable_scenario=applicable_scenario,
                keyword=keyword,
                tag=tag,
                min_success_rate=min_success_rate,
                page=page,
                page_size=page_size
            )

            result_list = []
            for strategy in strategies:
                item = {
                    "strategy_id": strategy.strategy_id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "applicable_scenarios": strategy.applicable_scenarios,
                    "success_rate": float(strategy.success_rate) if strategy.success_rate is not None else 0.0,
                    "tags": strategy.tags,
                    "usage_count": strategy.usage_count,
                    "created_at": strategy.created_at.isoformat() if strategy.created_at else None
                }
                result_list.append(item)

            return total, result_list

        except Exception as e:
            logger.error(f"查询策略列表失败: {str(e)}", exc_info=True)
            return 0, []

    @staticmethod
    async def get_factor_detail(
        db: AsyncSession,
        factor_id: str,
        include_related_templates: bool = False,
        template_limit: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取因子详情
        :param db: 数据库会话
        :param factor_id: 因子ID
        :param include_related_templates: 是否包含使用了该因子的模板列表
        :param template_limit: 包含模板时的返回数量限制
        :return: 因子详情字典，不存在时返回None
        """
        try:
            factor = await script_inspiration_template_dao.get_factor_by_factor_id(db, factor_id)
            if not factor:
                logger.warning(f"因子ID {factor_id} 不存在")
                return None

            result = {
                "factor_id": factor.factor_id,
                "factor_type": factor.factor_type,
                "name": factor.name,
                "description": factor.description,
                "applicable_scenarios": factor.applicable_scenarios,
                "data_schema": factor.data_schema,
                "example": factor.example,
                "tags": factor.tags,
                "popularity": float(factor.popularity) if factor.popularity is not None else 0.0,
                "usage_count": factor.usage_count,
                "created_at": factor.created_at.isoformat() if factor.created_at else None,
                "updated_at": factor.updated_at.isoformat() if factor.updated_at else None
            }

            # 包含关联的模板列表
            if include_related_templates:
                # 查询使用了该因子的模板（需要通过关联表查询）
                from sqlalchemy import select
                from backend.v1.app.models.inspiration_template import TemplateFactorRelation, InspirationTemplate

                query = select(
                    InspirationTemplate
                ).join(
                    TemplateFactorRelation,
                    TemplateFactorRelation.template_id == InspirationTemplate.template_id
                ).where(
                    TemplateFactorRelation.factor_id == factor_id,
                    InspirationTemplate.is_deleted == 0
                ).order_by(
                    InspirationTemplate.usage_count.desc(),
                    InspirationTemplate.success_rate.desc()
                ).limit(template_limit)

                result_ = await db.execute(query)
                templates = result_.scalars().all()

                result["related_templates"] = [
                    {
                        "template_id": t.template_id,
                        "name": t.name,
                        "success_rate": float(t.success_rate) if t.success_rate is not None else 0.0,
                        "usage_count": t.usage_count
                    } for t in templates
                ]

            return result

        except Exception as e:
            logger.error(f"获取因子详情失败: {str(e)}", exc_info=True)
            return None

    @staticmethod
    async def list_factors(
        db: AsyncSession,
        factor_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        min_popularity: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """分页查询因子列表
        :param db: 数据库会话
        :param factor_type: 按因子类型筛选（可选）
        :param keyword: 按名称/描述模糊搜索（可选）
        :param tag: 按标签筛选（可选）
        :param min_popularity: 最低流行度筛选（可选）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: (总数量, 因子列表)
        """
        try:
            total, factors = await script_inspiration_template_dao.list_factors(
                db=db,
                factor_type=factor_type,
                keyword=keyword,
                tag=tag,
                min_popularity=min_popularity,
                page=page,
                page_size=page_size
            )

            result_list = []
            for factor in factors:
                item = {
                    "factor_id": factor.factor_id,
                    "factor_type": factor.factor_type,
                    "name": factor.name,
                    "description": factor.description,
                    "tags": factor.tags,
                    "popularity": float(factor.popularity) if factor.popularity is not None else 0.0,
                    "usage_count": factor.usage_count,
                    "created_at": factor.created_at.isoformat() if factor.created_at else None
                }
                result_list.append(item)

            return total, result_list

        except Exception as e:
            logger.error(f"查询因子列表失败: {str(e)}", exc_info=True)
            return 0, []

    @staticmethod
    async def get_hot_recommendations(
        db: AsyncSession,
        template_limit: int = 10,
        strategy_limit: int = 5,
        factor_limit: int = 10
    ) -> Dict[str, Any]:
        """获取热门推荐
        :param db: 数据库会话
        :param template_limit: 热门模板返回数量
        :param strategy_limit: 热门策略返回数量
        :param factor_limit: 热门因子返回数量
        :return: 推荐结果字典
        """
        try:
            result = {
                "hot_templates": [],
                "hot_strategies": [],
                "hot_factors": []
            }

            # 获取热门模板
            hot_templates = await script_inspiration_template_dao.get_hot_templates(db, template_limit)
            result["hot_templates"] = [
                {
                    "template_id": t.template_id,
                    "name": t.name,
                    "description": t.description,
                    "success_rate": float(t.success_rate) if t.success_rate is not None else 0.0,
                    "usage_count": t.usage_count
                } for t in hot_templates
            ]

            # 获取热门策略
            _, hot_strategies = await script_inspiration_template_dao.list_strategies(
                db=db,
                page=1,
                page_size=strategy_limit
            )
            result["hot_strategies"] = [
                {
                    "strategy_id": s.strategy_id,
                    "name": s.name,
                    "description": s.description,
                    "success_rate": float(s.success_rate) if s.success_rate is not None else 0.0,
                    "usage_count": s.usage_count
                } for s in hot_strategies
            ]

            # 获取热门因子
            _, hot_factors = await script_inspiration_template_dao.list_factors(
                db=db,
                page=1,
                page_size=factor_limit
            )
            result["hot_factors"] = [
                {
                    "factor_id": f.factor_id,
                    "name": f.name,
                    "factor_type": f.factor_type,
                    "description": f.description,
                    "popularity": float(f.popularity) if f.popularity is not None else 0.0,
                    "usage_count": f.usage_count
                } for f in hot_factors
            ]

            return result

        except Exception as e:
            logger.error(f"获取热门推荐失败: {str(e)}", exc_info=True)
            return {"hot_templates": [], "hot_strategies": [], "hot_factors": []}

    @staticmethod
    async def search_all(
        db: AsyncSession,
        keyword: str,
        limit_per_type: int = 10
    ) -> Dict[str, Any]:
        """全局搜索模板、策略、因子
        :param db: 数据库会话
        :param keyword: 搜索关键词
        :param limit_per_type: 每种类型返回的最大数量
        :return: 搜索结果字典
        """
        try:
            result = {
                "templates": [],
                "strategies": [],
                "factors": []
            }

            # 搜索模板
            _, templates = await script_inspiration_template_dao.list_templates(
                db=db,
                keyword=keyword,
                page=1,
                page_size=limit_per_type
            )
            result["templates"] = [
                {
                    "template_id": t.template_id,
                    "name": t.name,
                    "description": t.description,
                    "type": "template"
                } for t in templates
            ]

            # 搜索策略
            _, strategies = await script_inspiration_template_dao.list_strategies(
                db=db,
                keyword=keyword,
                page=1,
                page_size=limit_per_type
            )
            result["strategies"] = [
                {
                    "strategy_id": s.strategy_id,
                    "name": s.name,
                    "description": s.description,
                    "type": "strategy"
                } for s in strategies
            ]

            # 搜索因子
            _, factors = await script_inspiration_template_dao.list_factors(
                db=db,
                keyword=keyword,
                page=1,
                page_size=limit_per_type
            )
            result["factors"] = [
                {
                    "factor_id": f.factor_id,
                    "name": f.name,
                    "description": f.description,
                    "type": "factor"
                } for f in factors
            ]

            return result

        except Exception as e:
            logger.error(f"全局搜索失败: {str(e)}", exc_info=True)
            return {"templates": [], "strategies": [], "factors": []}


# 模块级单例
inspiration_template_query_service = InspirationTemplateQueryService()
