"""灵感模板查询数据访问层

职责：封装script模块对灵感模板相关表的查询操作，Service层通过此层访问数据库。
仅提供查询功能，不包含写入、修改、删除等操作。
"""
from typing import Optional, List, Tuple
from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.inspiration_template import (
    Factor, Strategy, InspirationTemplate, TemplateFactorRelation
)


class ScriptInspirationTemplateDAO:
    """script模块灵感模板数据访问层"""

    @staticmethod
    async def get_template_by_template_id(db: AsyncSession, template_id: str) -> Optional[InspirationTemplate]:
        """根据全局唯一template_id查询模板
        :param db: 数据库会话
        :param template_id: 全局唯一模板ID
        :return: InspirationTemplate 对象，不存在返回 None
        """
        result = await db.execute(select(InspirationTemplate).where(
            InspirationTemplate.template_id == template_id,
            InspirationTemplate.is_deleted == 0
        ))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        strategy_id: Optional[str] = None,
        keyword: Optional[str] = None,
        version: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[InspirationTemplate]]:
        """分页查询模板列表
        :param db: 数据库会话
        :param strategy_id: 按关联策略ID筛选（可选）
        :param keyword: 按名称/描述模糊搜索（可选）
        :param version: 按版本号筛选（可选）
        :param min_success_rate: 最低成功率筛选（可选）
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: (总数量, 模板列表)
        """
        query = select(InspirationTemplate).where(InspirationTemplate.is_deleted == 0)

        # 按策略ID筛选
        if strategy_id:
            query = query.where(InspirationTemplate.strategy_id == strategy_id)

        # 按关键词搜索
        if keyword:
            query = query.where(
                or_(
                    InspirationTemplate.name.like(f"%{keyword}%"),
                    InspirationTemplate.description.like(f"%{keyword}%")
                )
            )

        # 按版本号筛选
        if version:
            query = query.where(InspirationTemplate.version == version)

        # 按最低成功率筛选
        if min_success_rate is not None:
            query = query.where(InspirationTemplate.success_rate >= min_success_rate)

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(
            InspirationTemplate.success_rate.desc(),
            InspirationTemplate.usage_count.desc(),
            InspirationTemplate.created_at.desc()
        ).offset(offset).limit(page_size)
        result = await db.execute(query)
        templates = result.scalars().all()

        return total, templates

    @staticmethod
    async def get_strategy_by_strategy_id(db: AsyncSession, strategy_id: str) -> Optional[Strategy]:
        """根据全局唯一strategy_id查询策略
        :param db: 数据库会话
        :param strategy_id: 全局唯一策略ID
        :return: Strategy 对象，不存在返回 None
        """
        result = await db.execute(select(Strategy).where(
            Strategy.strategy_id == strategy_id,
            Strategy.is_deleted == 0
        ))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_strategies(
        db: AsyncSession,
        applicable_scenario: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[Strategy]]:
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
        query = select(Strategy).where(Strategy.is_deleted == 0)

        # 按适用场景筛选
        if applicable_scenario:
            query = query.where(Strategy.applicable_scenarios.contains([applicable_scenario]))

        # 按关键词搜索
        if keyword:
            query = query.where(
                or_(
                    Strategy.name.like(f"%{keyword}%"),
                    Strategy.description.like(f"%{keyword}%")
                )
            )

        # 按标签筛选
        if tag:
            query = query.where(Strategy.tags.contains([tag]))

        # 按最低成功率筛选
        if min_success_rate is not None:
            query = query.where(Strategy.success_rate >= min_success_rate)

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(
            Strategy.success_rate.desc(),
            Strategy.usage_count.desc(),
            Strategy.created_at.desc()
        ).offset(offset).limit(page_size)
        result = await db.execute(query)
        strategies = result.scalars().all()

        return total, strategies

    @staticmethod
    async def get_factor_by_factor_id(db: AsyncSession, factor_id: str) -> Optional[Factor]:
        """根据全局唯一factor_id查询因子
        :param db: 数据库会话
        :param factor_id: 全局唯一因子ID
        :return: Factor 对象，不存在返回 None
        """
        result = await db.execute(select(Factor).where(
            Factor.factor_id == factor_id,
            Factor.is_deleted == 0
        ))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_factors(
        db: AsyncSession,
        factor_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        min_popularity: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[Factor]]:
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
        query = select(Factor).where(Factor.is_deleted == 0)

        # 按因子类型筛选
        if factor_type:
            query = query.where(Factor.factor_type == factor_type)

        # 按关键词搜索
        if keyword:
            query = query.where(
                or_(
                    Factor.name.like(f"%{keyword}%"),
                    Factor.description.like(f"%{keyword}%")
                )
            )

        # 按标签筛选
        if tag:
            query = query.where(Factor.tags.contains([tag]))

        # 按最低流行度筛选
        if min_popularity is not None:
            query = query.where(Factor.popularity >= min_popularity)

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(
            Factor.popularity.desc(),
            Factor.usage_count.desc(),
            Factor.created_at.desc()
        ).offset(offset).limit(page_size)
        result = await db.execute(query)
        factors = result.scalars().all()

        return total, factors

    @staticmethod
    async def get_template_factors(db: AsyncSession, template_id: str) -> List[dict]:
        """获取模板关联的因子列表（包含关联信息）
        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 因子列表，包含关联信息
        """
        query = select(
            TemplateFactorRelation,
            Factor
        ).join(
            Factor,
            TemplateFactorRelation.factor_id == Factor.factor_id
        ).where(
            TemplateFactorRelation.template_id == template_id,
            Factor.is_deleted == 0
        ).order_by(
            TemplateFactorRelation.sort_order,
            Factor.popularity.desc()
        )

        result = await db.execute(query)
        rows = result.all()

        factors = []
        for relation, factor in rows:
            factors.append({
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
                "factor_usage_type": relation.factor_usage_type,
                "sort_order": relation.sort_order
            })

        return factors

    @staticmethod
    async def get_hot_templates(
        db: AsyncSession,
        limit: int = 10
    ) -> List[InspirationTemplate]:
        """获取热门模板
        :param db: 数据库会话
        :param limit: 返回数量
        :return: 热门模板列表
        """
        query = select(InspirationTemplate).where(
            InspirationTemplate.is_deleted == 0
        ).order_by(
            InspirationTemplate.usage_count.desc(),
            InspirationTemplate.success_rate.desc(),
            InspirationTemplate.created_at.desc()
        ).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()


# 模块级单例
script_inspiration_template_dao = ScriptInspirationTemplateDAO()
