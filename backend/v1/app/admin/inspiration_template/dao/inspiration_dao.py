"""灵感模板数据访问层

职责：封装所有对灵感模板相关表的数据库操作，Service 层通过此层访问数据库。
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.v1.app.models.inspiration_template import (
    Factor, Strategy, InspirationTemplate, TemplateFactorRelation
)


class FactorDAO:
    """创作因子数据访问层"""

    @staticmethod
    def create_factor(db: Session, factor_data: dict) -> Factor:
        """创建因子记录

        :param db: 数据库会话
        :param factor_data: 因子字段字典
        :return: 创建后的 Factor 对象
        """
        factor = Factor(**factor_data)
        db.add(factor)
        db.commit()
        db.refresh(factor)
        return factor

    @staticmethod
    def get_factor_by_id(db: Session, factor_id: int) -> Optional[Factor]:
        """根据因子ID查询因子

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :return: Factor 对象，不存在返回 None
        """
        return db.query(Factor).filter(Factor.id == factor_id, Factor.is_deleted == 0).first()

    @staticmethod
    def get_factor_by_factor_id(db: Session, factor_id: str) -> Optional[Factor]:
        """根据全局唯一factor_id查询因子

        :param db: 数据库会话
        :param factor_id: 全局唯一因子ID
        :return: Factor 对象，不存在返回 None
        """
        return db.query(Factor).filter(Factor.factor_id == factor_id, Factor.is_deleted == 0).first()

    @staticmethod
    def update_factor(db: Session, factor_id: int, update_data: dict) -> Optional[Factor]:
        """更新因子信息

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 Factor 对象
        """
        db.query(Factor).filter(Factor.id == factor_id, Factor.is_deleted == 0).update(update_data)
        db.commit()
        return FactorDAO.get_factor_by_id(db, factor_id)

    @staticmethod
    def delete_factor(db: Session, factor_id: int) -> bool:
        """软删除因子

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :return: 删除是否成功
        """
        result = db.query(Factor).filter(Factor.id == factor_id, Factor.is_deleted == 0).update({"is_deleted": 1})
        db.commit()
        return result > 0

    @staticmethod
    def list_factors(
        db: Session,
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
        query = db.query(Factor).filter(Factor.is_deleted == 0)

        # 按因子类型筛选
        if factor_type:
            query = query.filter(Factor.factor_type == factor_type)

        # 按关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    Factor.name.like(f"%{keyword}%"),
                    Factor.description.like(f"%{keyword}%")
                )
            )

        # 按标签筛选
        if tag:
            query = query.filter(Factor.tags.contains([tag]))

        total = query.count()
        offset = (page - 1) * page_size
        factors = query.order_by(Factor.popularity.desc(), Factor.created_at.desc()).offset(offset).limit(page_size).all()

        return total, factors


class StrategyDAO:
    """创作策略数据访问层"""

    @staticmethod
    def create_strategy(db: Session, strategy_data: dict) -> Strategy:
        """创建策略记录

        :param db: 数据库会话
        :param strategy_data: 策略字段字典
        :return: 创建后的 Strategy 对象
        """
        strategy = Strategy(**strategy_data)
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        return strategy

    @staticmethod
    def get_strategy_by_id(db: Session, strategy_id: int) -> Optional[Strategy]:
        """根据策略ID查询策略

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :return: Strategy 对象，不存在返回 None
        """
        return db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted == 0).first()

    @staticmethod
    def get_strategy_by_strategy_id(db: Session, strategy_id: str) -> Optional[Strategy]:
        """根据全局唯一strategy_id查询策略

        :param db: 数据库会话
        :param strategy_id: 全局唯一策略ID
        :return: Strategy 对象，不存在返回 None
        """
        return db.query(Strategy).filter(Strategy.strategy_id == strategy_id, Strategy.is_deleted == 0).first()

    @staticmethod
    def update_strategy(db: Session, strategy_id: int, update_data: dict) -> Optional[Strategy]:
        """更新策略信息

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 Strategy 对象
        """
        db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted == 0).update(update_data)
        db.commit()
        return StrategyDAO.get_strategy_by_id(db, strategy_id)

    @staticmethod
    def delete_strategy(db: Session, strategy_id: int) -> bool:
        """软删除策略

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :return: 删除是否成功
        """
        result = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_deleted == 0).update({"is_deleted": 1})
        db.commit()
        return result > 0

    @staticmethod
    def list_strategies(
        db: Session,
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
        query = db.query(Strategy).filter(Strategy.is_deleted == 0)

        # 按适用场景筛选
        if applicable_scenario:
            query = query.filter(Strategy.applicable_scenarios.contains([applicable_scenario]))

        # 按关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    Strategy.name.like(f"%{keyword}%"),
                    Strategy.description.like(f"%{keyword}%")
                )
            )

        # 按标签筛选
        if tag:
            query = query.filter(Strategy.tags.contains([tag]))

        # 按最低成功率筛选
        if min_success_rate is not None:
            query = query.filter(Strategy.success_rate >= min_success_rate)

        total = query.count()
        offset = (page - 1) * page_size
        strategies = query.order_by(Strategy.success_rate.desc(), Strategy.created_at.desc()).offset(offset).limit(page_size).all()

        return total, strategies


class InspirationTemplateDAO:
    """灵感模板数据访问层"""

    @staticmethod
    def create_template(db: Session, template_data: dict) -> InspirationTemplate:
        """创建模板记录

        :param db: 数据库会话
        :param template_data: 模板字段字典
        :return: 创建后的 InspirationTemplate 对象
        """
        template = InspirationTemplate(**template_data)
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    @staticmethod
    def get_template_by_id(db: Session, template_id: int) -> Optional[InspirationTemplate]:
        """根据模板ID查询模板

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: InspirationTemplate 对象，不存在返回 None
        """
        return db.query(InspirationTemplate).filter(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0).first()

    @staticmethod
    def get_template_by_template_id(db: Session, template_id: str) -> Optional[InspirationTemplate]:
        """根据全局唯一template_id查询模板

        :param db: 数据库会话
        :param template_id: 全局唯一模板ID
        :return: InspirationTemplate 对象，不存在返回 None
        """
        return db.query(InspirationTemplate).filter(InspirationTemplate.template_id == template_id, InspirationTemplate.is_deleted == 0).first()

    @staticmethod
    def update_template(db: Session, template_id: int, update_data: dict) -> Optional[InspirationTemplate]:
        """更新模板信息

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 InspirationTemplate 对象
        """
        db.query(InspirationTemplate).filter(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0).update(update_data)
        db.commit()
        return InspirationTemplateDAO.get_template_by_id(db, template_id)

    @staticmethod
    def delete_template(db: Session, template_id: int) -> bool:
        """软删除模板

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: 删除是否成功
        """
        result = db.query(InspirationTemplate).filter(InspirationTemplate.id == template_id, InspirationTemplate.is_deleted == 0).update({"is_deleted": 1})
        db.commit()
        return result > 0

    @staticmethod
    def list_templates(
        db: Session,
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
        query = db.query(InspirationTemplate).filter(InspirationTemplate.is_deleted == 0)

        # 按策略ID筛选
        if strategy_id:
            query = query.filter(InspirationTemplate.strategy_id == strategy_id)

        # 按关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    InspirationTemplate.name.like(f"%{keyword}%"),
                    InspirationTemplate.description.like(f"%{keyword}%")
                )
            )

        # 按版本号筛选
        if version:
            query = query.filter(InspirationTemplate.version == version)

        # 按最低成功率筛选
        if min_success_rate is not None:
            query = query.filter(InspirationTemplate.success_rate >= min_success_rate)

        total = query.count()
        offset = (page - 1) * page_size
        templates = query.order_by(InspirationTemplate.success_rate.desc(), InspirationTemplate.created_at.desc()).offset(offset).limit(page_size).all()

        return total, templates


class TemplateFactorRelationDAO:
    """模板-因子关联数据访问层"""

    @staticmethod
    def create_relation(db: Session, relation_data: dict) -> TemplateFactorRelation:
        """创建关联记录

        :param db: 数据库会话
        :param relation_data: 关联字段字典
        :return: 创建后的 TemplateFactorRelation 对象
        """
        relation = TemplateFactorRelation(**relation_data)
        db.add(relation)
        db.commit()
        db.refresh(relation)
        return relation

    @staticmethod
    def batch_create_relations(db: Session, relations_data: List[dict]) -> List[TemplateFactorRelation]:
        """批量创建关联记录

        :param db: 数据库会话
        :param relations_data: 关联字段字典列表
        :return: 创建后的 TemplateFactorRelation 对象列表
        """
        relations = [TemplateFactorRelation(**data) for data in relations_data]
        db.bulk_save_objects(relations)
        db.commit()
        return relations

    @staticmethod
    def get_relation_by_id(db: Session, relation_id: int) -> Optional[TemplateFactorRelation]:
        """根据关联ID查询关联

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :return: TemplateFactorRelation 对象，不存在返回 None
        """
        return db.query(TemplateFactorRelation).filter(TemplateFactorRelation.id == relation_id).first()

    @staticmethod
    def get_relations_by_template_id(db: Session, template_id: str) -> List[TemplateFactorRelation]:
        """根据模板ID查询所有关联的因子

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 关联关系列表
        """
        return db.query(TemplateFactorRelation).filter(TemplateFactorRelation.template_id == template_id).order_by(TemplateFactorRelation.sort_order).all()

    @staticmethod
    def get_relations_by_factor_id(db: Session, factor_id: str) -> List[TemplateFactorRelation]:
        """根据因子ID查询所有关联的模板

        :param db: 数据库会话
        :param factor_id: 因子ID
        :return: 关联关系列表
        """
        return db.query(TemplateFactorRelation).filter(TemplateFactorRelation.factor_id == factor_id).all()

    @staticmethod
    def update_relation(db: Session, relation_id: int, update_data: dict) -> Optional[TemplateFactorRelation]:
        """更新关联信息

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :param update_data: 需要更新的字段字典
        :return: 更新后的 TemplateFactorRelation 对象
        """
        db.query(TemplateFactorRelation).filter(TemplateFactorRelation.id == relation_id).update(update_data)
        db.commit()
        return TemplateFactorRelationDAO.get_relation_by_id(db, relation_id)

    @staticmethod
    def delete_relation(db: Session, relation_id: int) -> bool:
        """删除关联

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :return: 删除是否成功
        """
        result = db.query(TemplateFactorRelation).filter(TemplateFactorRelation.id == relation_id).delete()
        db.commit()
        return result > 0

    @staticmethod
    def delete_relations_by_template_id(db: Session, template_id: str) -> int:
        """删除模板下的所有关联

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 删除的数量
        """
        result = db.query(TemplateFactorRelation).filter(TemplateFactorRelation.template_id == template_id).delete()
        db.commit()
        return result
