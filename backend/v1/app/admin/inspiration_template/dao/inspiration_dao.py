"""灵感模板数据访问层

职责：封装所有对灵感模板相关表的数据库操作，Service 层通过此层访问数据库。
"""
from typing import Optional, List, Tuple
from sqlalchemy import and_, or_, select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.inspiration_template import (
    Factor, Strategy, InspirationTemplate, TemplateFactorRelation
)


class FactorDAO:
    """创作因子数据访问层"""

    @staticmethod
    async def create_factor(db: AsyncSession, factor_data: dict) -> Factor:
        """创建因子记录

        :param db: 数据库会话
        :param factor_data: 因子字段字典
        :return: 创建后的 Factor 对象
        """
        factor = Factor(**factor_data)
        db.add(factor)
        await db.commit()
        await db.refresh(factor)
        return factor

    @staticmethod
    async def get_factor_by_id(db: AsyncSession, factor_id: int) -> Optional[Factor]:
        """根据因子ID查询因子

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :return: Factor 对象，不存在返回 None
        """
        result = await db.execute(select(Factor).where(Factor.id == factor_id, Factor.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_factor_by_factor_id(db: AsyncSession, factor_id: str) -> Optional[Factor]:
        """根据全局唯一factor_id查询因子

        :param db: 数据库会话
        :param factor_id: 全局唯一因子ID
        :return: Factor 对象，不存在返回 None
        """
        result = await db.execute(select(Factor).where(Factor.factor_id == factor_id, Factor.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_factor(db: AsyncSession, factor_id: int, update_data: dict) -> Optional[Factor]:
        """更新因子信息

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 Factor 对象
        """
        stmt = update(Factor).where(Factor.id == factor_id, Factor.is_deleted == 0).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await FactorDAO.get_factor_by_id(db, factor_id)

    @staticmethod
    async def delete_factor(db: AsyncSession, factor_id: int) -> bool:
        """软删除因子

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :return: 删除是否成功
        """
        stmt = update(Factor).where(Factor.id == factor_id, Factor.is_deleted == 0).values(is_deleted=1)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def list_factors(
        db: AsyncSession,
        factor_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[Factor]]:
        """分页查询因子列表

        :param db: 数据库会话
        :param factor_type: 按因子类型筛选（可选）
        :param keyword: 按名称/描述模糊搜索（可选）
        :param tag: 按标签筛选（可选）
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

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(Factor.popularity.desc(), Factor.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        factors = result.scalars().all()

        return total, factors

    @staticmethod
    async def count_factors(db: AsyncSession) -> int:
        """统计有效因子总数

        :param db: 数据库会话
        :return: 因子总数
        """
        count_query = select(func.count()).select_from(
            select(Factor).where(Factor.is_deleted == 0).subquery()
        )
        total = await db.scalar(count_query) or 0
        return total

    @staticmethod
    async def list_all_factors(db: AsyncSession, min_usage: Optional[int] = None) -> List[Factor]:
        """查询所有有效因子（不分页，供图谱使用）

        :param db: 数据库会话
        :param min_usage: 最小使用次数筛选（可选）
        :return: 因子列表
        """
        # 暂时去掉is_deleted条件调试
        query = select(Factor)

        if min_usage is not None:
            query = query.where(Factor.usage_count >= min_usage)

        query = query.order_by(Factor.popularity.desc(), Factor.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()


class StrategyDAO:
    """创作策略数据访问层"""

    @staticmethod
    async def create_strategy(db: AsyncSession, strategy_data: dict) -> Strategy:
        """创建策略记录

        :param db: 数据库会话
        :param strategy_data: 策略字段字典
        :return: 创建后的 Strategy 对象
        """
        strategy = Strategy(**strategy_data)
        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)
        return strategy

    @staticmethod
    async def get_strategy_by_id(db: AsyncSession, strategy_id: int) -> Optional[Strategy]:
        """根据策略ID查询策略

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :return: Strategy 对象，不存在返回 None
        """
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id, Strategy.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_strategy_by_strategy_id(db: AsyncSession, strategy_id: str) -> Optional[Strategy]:
        """根据全局唯一strategy_id查询策略

        :param db: 数据库会话
        :param strategy_id: 全局唯一策略ID
        :return: Strategy 对象，不存在返回 None
        """
        result = await db.execute(select(Strategy).where(Strategy.strategy_id == strategy_id, Strategy.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_strategy(db: AsyncSession, strategy_id: int, update_data: dict) -> Optional[Strategy]:
        """更新策略信息

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 Strategy 对象
        """
        stmt = update(Strategy).where(Strategy.id == strategy_id, Strategy.is_deleted == 0).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await StrategyDAO.get_strategy_by_id(db, strategy_id)

    @staticmethod
    async def delete_strategy(db: AsyncSession, strategy_id: int) -> bool:
        """软删除策略

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :return: 删除是否成功
        """
        stmt = update(Strategy).where(Strategy.id == strategy_id, Strategy.is_deleted == 0).values(is_deleted=1)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

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
        query = query.order_by(Strategy.success_rate.desc(), Strategy.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        strategies = result.scalars().all()

        return total, strategies

    @staticmethod
    async def count_strategies(db: AsyncSession) -> int:
        """统计有效策略总数

        :param db: 数据库会话
        :return: 策略总数
        """
        count_query = select(func.count()).select_from(
            select(Strategy).where(Strategy.is_deleted == 0).subquery()
        )
        total = await db.scalar(count_query) or 0
        return total

    @staticmethod
    async def list_all_strategies(db: AsyncSession, min_usage: Optional[int] = None, min_success_rate: Optional[float] = None) -> List[Strategy]:
        """查询所有有效策略（不分页，供图谱使用）

        :param db: 数据库会话
        :param min_usage: 最小使用次数筛选（可选）
        :param min_success_rate: 最低成功率筛选（可选）
        :return: 策略列表
        """
        # 暂时去掉is_deleted条件调试
        query = select(Strategy)

        if min_usage is not None:
            query = query.where(Strategy.usage_count >= min_usage)
        if min_success_rate is not None:
            query = query.where(Strategy.success_rate >= min_success_rate)

        query = query.order_by(Strategy.success_rate.desc(), Strategy.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()


class InspirationTemplateDAO:
    """灵感模板数据访问层"""

    @staticmethod
    async def create_template(db: AsyncSession, template_data: dict) -> InspirationTemplate:
        """创建模板记录

        :param db: 数据库会话
        :param template_data: 模板字段字典
        :return: 创建后的 InspirationTemplate 对象
        """
        template = InspirationTemplate(**template_data)
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def get_template_by_id(db: AsyncSession, template_id: int) -> Optional[InspirationTemplate]:
        """根据模板ID查询模板

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: InspirationTemplate 对象，不存在返回 None
        """
        result = await db.execute(select(InspirationTemplate).where(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_template_by_template_id(db: AsyncSession, template_id: str) -> Optional[InspirationTemplate]:
        """根据全局唯一template_id查询模板

        :param db: 数据库会话
        :param template_id: 全局唯一模板ID
        :return: InspirationTemplate 对象，不存在返回 None
        """
        result = await db.execute(select(InspirationTemplate).where(InspirationTemplate.template_id == template_id, InspirationTemplate.is_deleted == 0))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_template(db: AsyncSession, template_id: int, update_data: dict) -> Optional[InspirationTemplate]:
        """更新模板信息

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 InspirationTemplate 对象
        """
        stmt = update(InspirationTemplate).where(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await InspirationTemplateDAO.get_template_by_id(db, template_id)

    @staticmethod
    async def delete_template(db: AsyncSession, template_id: int) -> bool:
        """软删除模板

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: 删除是否成功
        """
        stmt = update(InspirationTemplate).where(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0).values(is_deleted=1)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

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
        query = query.order_by(InspirationTemplate.success_rate.desc(), InspirationTemplate.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        templates = result.scalars().all()

        return total, templates

    @staticmethod
    async def count_templates(db: AsyncSession) -> int:
        """统计有效模板总数

        :param db: 数据库会话
        :return: 模板总数
        """
        count_query = select(func.count()).select_from(
            select(InspirationTemplate).where(InspirationTemplate.is_deleted == 0).subquery()
        )
        total = await db.scalar(count_query) or 0
        return total

    @staticmethod
    async def list_all_templates(db: AsyncSession, min_usage: Optional[int] = None, min_success_rate: Optional[float] = None) -> List[InspirationTemplate]:
        """查询所有有效模板（不分页，供图谱使用）

        :param db: 数据库会话
        :param min_usage: 最小使用次数筛选（可选）
        :param min_success_rate: 最低成功率筛选（可选）
        :return: 模板列表
        """
        query = select(InspirationTemplate).where(InspirationTemplate.is_deleted == 0)

        if min_usage is not None:
            query = query.where(InspirationTemplate.usage_count >= min_usage)
        if min_success_rate is not None:
            query = query.where(InspirationTemplate.success_rate >= min_success_rate)

        query = query.order_by(InspirationTemplate.success_rate.desc(), InspirationTemplate.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()


class TemplateFactorRelationDAO:
    """模板-因子关联数据访问层"""

    @staticmethod
    async def create_relation(db: AsyncSession, relation_data: dict) -> TemplateFactorRelation:
        """创建关联记录

        :param db: 数据库会话
        :param relation_data: 关联字段字典
        :return: 创建后的 TemplateFactorRelation 对象
        """
        relation = TemplateFactorRelation(**relation_data)
        db.add(relation)
        await db.commit()
        await db.refresh(relation)
        return relation

    @staticmethod
    async def batch_create_relations(db: AsyncSession, relations_data: List[dict]) -> List[TemplateFactorRelation]:
        """批量创建关联记录

        :param db: 数据库会话
        :param relations_data: 关联字段字典列表
        :return: 创建后的 TemplateFactorRelation 对象列表
        """
        relations = [TemplateFactorRelation(**data) for data in relations_data]
        db.add_all(relations)
        await db.commit()
        # 批量刷新需要单独处理
        for relation in relations:
            await db.refresh(relation)
        return relations

    @staticmethod
    async def get_relation_by_id(db: AsyncSession, relation_id: int) -> Optional[TemplateFactorRelation]:
        """根据关联ID查询关联

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :return: TemplateFactorRelation 对象，不存在返回 None
        """
        result = await db.execute(select(TemplateFactorRelation).where(TemplateFactorRelation.id == relation_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_relations_by_template_id(db: AsyncSession, template_id: str) -> List[TemplateFactorRelation]:
        """根据模板ID查询所有关联的因子

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 关联关系列表
        """
        query = select(TemplateFactorRelation).where(TemplateFactorRelation.template_id == template_id).order_by(TemplateFactorRelation.sort_order)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_relations_by_factor_id(db: AsyncSession, factor_id: str) -> List[TemplateFactorRelation]:
        """根据因子ID查询所有关联的模板

        :param db: 数据库会话
        :param factor_id: 因子ID
        :return: 关联关系列表
        """
        query = select(TemplateFactorRelation).where(TemplateFactorRelation.factor_id == factor_id)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_relation(db: AsyncSession, relation_id: int, update_data: dict) -> Optional[TemplateFactorRelation]:
        """更新关联信息

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 TemplateFactorRelation 对象
        """
        stmt = update(TemplateFactorRelation).where(TemplateFactorRelation.id == relation_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await TemplateFactorRelationDAO.get_relation_by_id(db, relation_id)

    @staticmethod
    async def delete_relation(db: AsyncSession, relation_id: int) -> bool:
        """删除关联

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :return: 删除是否成功
        """
        stmt = delete(TemplateFactorRelation).where(TemplateFactorRelation.id == relation_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_relations_by_template_id(db: AsyncSession, template_id: str) -> int:
        """删除模板下的所有关联

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 删除的数量
        """
        stmt = delete(TemplateFactorRelation).where(TemplateFactorRelation.template_id == template_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def list_all_relations(db: AsyncSession) -> List[TemplateFactorRelation]:
        """查询所有模板-因子关联关系（供图谱使用）

        :param db: 数据库会话
        :return: 关联关系列表
        """
        query = select(TemplateFactorRelation).order_by(TemplateFactorRelation.sort_order)
        result = await db.execute(query)
        return result.scalars().all()
