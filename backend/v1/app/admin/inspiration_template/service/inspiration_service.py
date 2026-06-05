"""灵感模板业务逻辑层

职责：处理灵感模板相关的业务逻辑，包括因子、策略、模板的CRUD操作，关联数据组装等。
不直接操作数据库，通过 DAO 层访问数据层。
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid

from backend.v1.app.models.inspiration_template import (
    Factor, Strategy, InspirationTemplate, TemplateFactorRelation
)
from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO, TemplateFactorRelationDAO
)
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import (
    RESOURCE_NOT_FOUND,
    RESOURCE_ALREADY_EXISTS,
    PARAM_ERROR,
)


class FactorService:
    """创作因子业务逻辑层"""

    @staticmethod
    def generate_factor_id() -> str:
        """生成全局唯一的factor_id"""
        return f"factor_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def create_factor(db: Session, factor_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建因子

        :param db: 数据库会话
        :param factor_data: 因子数据
        :return: 创建后的因子信息
        :raises BusinessException: factor_id已存在时抛出异常
        """
        # 如果没有提供factor_id，自动生成
        if not factor_data.get("factor_id"):
            factor_data["factor_id"] = FactorService.generate_factor_id()
        else:
            # 检查factor_id是否已存在
            existing = FactorDAO.get_factor_by_factor_id(db, factor_data["factor_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "因子ID已存在")

        factor = FactorDAO.create_factor(db, factor_data)
        return FactorService._factor_to_dict(factor)

    @staticmethod
    def get_factor(db: Session, factor_id: int) -> Dict[str, Any]:
        """获取因子详情

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :return: 因子信息
        :raises BusinessException: 因子不存在时抛出异常
        """
        factor = FactorDAO.get_factor_by_id(db, factor_id)
        if not factor:
            raise BusinessException(RESOURCE_NOT_FOUND, "因子不存在")
        return FactorService._factor_to_dict(factor)

    @staticmethod
    def update_factor(db: Session, factor_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新因子信息

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :param update_data: 需要更新的字段
        :return: 更新后的因子信息
        :raises BusinessException: 因子不存在时抛出异常
        """
        factor = FactorDAO.get_factor_by_id(db, factor_id)
        if not factor:
            raise BusinessException(RESOURCE_NOT_FOUND, "因子不存在")

        # 如果要更新factor_id，检查是否已存在
        if "factor_id" in update_data and update_data["factor_id"] != factor.factor_id:
            existing = FactorDAO.get_factor_by_factor_id(db, update_data["factor_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "因子ID已存在")

        updated_factor = FactorDAO.update_factor(db, factor_id, update_data)
        return FactorService._factor_to_dict(updated_factor)

    @staticmethod
    def delete_factor(db: Session, factor_id: int) -> None:
        """删除因子

        :param db: 数据库会话
        :param factor_id: 因子主键ID
        :raises BusinessException: 因子不存在或被引用时抛出异常
        """
        factor = FactorDAO.get_factor_by_id(db, factor_id)
        if not factor:
            raise BusinessException(RESOURCE_NOT_FOUND, "因子不存在")

        # 检查因子是否被模板引用
        relations = TemplateFactorRelationDAO.get_relations_by_factor_id(db, factor.factor_id)
        if relations:
            raise BusinessException(PARAM_ERROR, "该因子已被模板引用，无法删除")

        success = FactorDAO.delete_factor(db, factor_id)
        if not success:
            raise BusinessException(RESOURCE_NOT_FOUND, "因子不存在")

    @staticmethod
    def list_factors(
        db: Session,
        factor_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """分页查询因子列表

        :param db: 数据库会话
        :param factor_type: 因子类型筛选
        :param keyword: 关键词搜索
        :param tag: 标签筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果
        """
        total, factors = FactorDAO.list_factors(
            db, factor_type=factor_type, keyword=keyword, tag=tag, page=page, page_size=page_size
        )
        factor_list = [FactorService._factor_to_dict(f) for f in factors]
        return {
            "list": factor_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }

    @staticmethod
    def _factor_to_dict(factor: Factor) -> Dict[str, Any]:
        """将Factor对象转换为字典"""
        return {
            "id": factor.id,
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
            "created_at": factor.created_at.isoformat() if factor.created_at else "",
            "updated_at": factor.updated_at.isoformat() if factor.updated_at else "",
        }


class StrategyService:
    """创作策略业务逻辑层"""

    @staticmethod
    def generate_strategy_id() -> str:
        """生成全局唯一的strategy_id"""
        return f"strategy_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def create_strategy(db: Session, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建策略

        :param db: 数据库会话
        :param strategy_data: 策略数据
        :return: 创建后的策略信息
        :raises BusinessException: strategy_id已存在时抛出异常
        """
        # 如果没有提供strategy_id，自动生成
        if not strategy_data.get("strategy_id"):
            strategy_data["strategy_id"] = StrategyService.generate_strategy_id()
        else:
            # 检查strategy_id是否已存在
            existing = StrategyDAO.get_strategy_by_strategy_id(db, strategy_data["strategy_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "策略ID已存在")

        strategy = StrategyDAO.create_strategy(db, strategy_data)
        return StrategyService._strategy_to_dict(strategy)

    @staticmethod
    def get_strategy(db: Session, strategy_id: int) -> Dict[str, Any]:
        """获取策略详情

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :return: 策略信息
        :raises BusinessException: 策略不存在时抛出异常
        """
        strategy = StrategyDAO.get_strategy_by_id(db, strategy_id)
        if not strategy:
            raise BusinessException(RESOURCE_NOT_FOUND, "策略不存在")
        return StrategyService._strategy_to_dict(strategy)

    @staticmethod
    def update_strategy(db: Session, strategy_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新策略信息

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :param update_data: 需要更新的字段
        :return: 更新后的策略信息
        :raises BusinessException: 策略不存在时抛出异常
        """
        strategy = StrategyDAO.get_strategy_by_id(db, strategy_id)
        if not strategy:
            raise BusinessException(RESOURCE_NOT_FOUND, "策略不存在")

        # 如果要更新strategy_id，检查是否已存在
        if "strategy_id" in update_data and update_data["strategy_id"] != strategy.strategy_id:
            existing = StrategyDAO.get_strategy_by_strategy_id(db, update_data["strategy_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "策略ID已存在")

        updated_strategy = StrategyDAO.update_strategy(db, strategy_id, update_data)
        return StrategyService._strategy_to_dict(updated_strategy)

    @staticmethod
    def delete_strategy(db: Session, strategy_id: int) -> None:
        """删除策略

        :param db: 数据库会话
        :param strategy_id: 策略主键ID
        :raises BusinessException: 策略不存在或被引用时抛出异常
        """
        strategy = StrategyDAO.get_strategy_by_id(db, strategy_id)
        if not strategy:
            raise BusinessException(RESOURCE_NOT_FOUND, "策略不存在")

        # 检查策略是否被模板引用
        templates = InspirationTemplateDAO.list_templates(db, strategy_id=strategy.strategy_id)
        if templates[0] > 0:
            raise BusinessException(PARAM_ERROR, "该策略已被模板引用，无法删除")

        success = StrategyDAO.delete_strategy(db, strategy_id)
        if not success:
            raise BusinessException(RESOURCE_NOT_FOUND, "策略不存在")

    @staticmethod
    def list_strategies(
        db: Session,
        applicable_scenario: Optional[str] = None,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """分页查询策略列表

        :param db: 数据库会话
        :param applicable_scenario: 适用场景筛选
        :param keyword: 关键词搜索
        :param tag: 标签筛选
        :param min_success_rate: 最低成功率筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果
        """
        total, strategies = StrategyDAO.list_strategies(
            db, applicable_scenario=applicable_scenario, keyword=keyword, tag=tag,
            min_success_rate=min_success_rate, page=page, page_size=page_size
        )
        strategy_list = [StrategyService._strategy_to_dict(s) for s in strategies]
        return {
            "list": strategy_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }

    @staticmethod
    def _strategy_to_dict(strategy: Strategy) -> Dict[str, Any]:
        """将Strategy对象转换为字典"""
        return {
            "id": strategy.id,
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
            "created_at": strategy.created_at.isoformat() if strategy.created_at else "",
            "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else "",
        }


class InspirationTemplateService:
    """灵感模板业务逻辑层"""

    @staticmethod
    def generate_template_id() -> str:
        """生成全局唯一的template_id"""
        return f"template_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def create_template(db: Session, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建模板

        :param db: 数据库会话
        :param template_data: 模板数据，包含factor_relations字段
        :return: 创建后的模板信息（包含关联的策略和因子）
        :raises BusinessException: template_id已存在、策略不存在、因子不存在时抛出异常
        """
        # 提取关联因子数据
        factor_relations = template_data.pop("factor_relations", [])

        # 如果没有提供template_id，自动生成
        if not template_data.get("template_id"):
            template_data["template_id"] = InspirationTemplateService.generate_template_id()
        else:
            # 检查template_id是否已存在
            existing = InspirationTemplateDAO.get_template_by_template_id(db, template_data["template_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "模板ID已存在")

        # 检查关联的策略是否存在
        strategy_id = template_data.get("strategy_id")
        if strategy_id:
            strategy = StrategyDAO.get_strategy_by_strategy_id(db, strategy_id)
            if not strategy:
                raise BusinessException(RESOURCE_NOT_FOUND, f"策略ID {strategy_id} 不存在")

        # 创建模板
        template = InspirationTemplateDAO.create_template(db, template_data)

        # 创建关联因子
        if factor_relations:
            relations_data = []
            for rel in factor_relations:
                # 检查因子是否存在
                factor = FactorDAO.get_factor_by_factor_id(db, rel["factor_id"])
                if not factor:
                    raise BusinessException(RESOURCE_NOT_FOUND, f"因子ID {rel['factor_id']} 不存在")

                relations_data.append({
                    "template_id": template.template_id,
                    "factor_id": rel["factor_id"],
                    "factor_usage_type": rel["factor_usage_type"],
                    "sort_order": rel.get("sort_order", 0)
                })

            TemplateFactorRelationDAO.batch_create_relations(db, relations_data)

        # 返回完整的模板信息
        return InspirationTemplateService.get_template_detail(db, template.id)

    @staticmethod
    def get_template(db: Session, template_id: int) -> Dict[str, Any]:
        """获取模板基本信息

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: 模板基本信息
        :raises BusinessException: 模板不存在时抛出异常
        """
        template = InspirationTemplateDAO.get_template_by_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")
        return InspirationTemplateService._template_to_dict(template)

    @staticmethod
    def get_template_detail(db: Session, template_id: int) -> Dict[str, Any]:
        """获取模板详细信息（包含关联的策略和因子）

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :return: 模板详细信息
        :raises BusinessException: 模板不存在时抛出异常
        """
        template = InspirationTemplateDAO.get_template_by_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")

        # 组装返回数据
        result = InspirationTemplateService._template_to_dict(template)

        # 查询关联的策略
        strategy = StrategyDAO.get_strategy_by_strategy_id(db, template.strategy_id)
        if strategy:
            result["strategy"] = StrategyService._strategy_to_dict(strategy)

        # 查询关联的因子
        relations = TemplateFactorRelationDAO.get_relations_by_template_id(db, template.template_id)
        required_factors = []
        optional_factors = []

        for rel in relations:
            factor = FactorDAO.get_factor_by_factor_id(db, rel.factor_id)
            if factor:
                factor_dict = FactorService._factor_to_dict(factor)
                factor_dict["factor_usage_type"] = rel.factor_usage_type
                factor_dict["sort_order"] = rel.sort_order

                if rel.factor_usage_type == 1:
                    required_factors.append(factor_dict)
                else:
                    optional_factors.append(factor_dict)

        result["required_factors"] = required_factors
        result["optional_factors"] = optional_factors

        return result

    @staticmethod
    def update_template(db: Session, template_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新模板信息

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :param update_data: 需要更新的字段，包含factor_relations字段时会全量更新关联
        :return: 更新后的模板详细信息
        :raises BusinessException: 模板不存在、策略不存在、因子不存在时抛出异常
        """
        template = InspirationTemplateDAO.get_template_by_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")

        # 提取关联因子数据
        factor_relations = update_data.pop("factor_relations", None)

        # 如果要更新strategy_id，检查策略是否存在
        if "strategy_id" in update_data and update_data["strategy_id"] != template.strategy_id:
            strategy = StrategyDAO.get_strategy_by_strategy_id(db, update_data["strategy_id"])
            if not strategy:
                raise BusinessException(RESOURCE_NOT_FOUND, f"策略ID {update_data['strategy_id']} 不存在")

        # 如果要更新template_id，检查是否已存在
        if "template_id" in update_data and update_data["template_id"] != template.template_id:
            existing = InspirationTemplateDAO.get_template_by_template_id(db, update_data["template_id"])
            if existing:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "模板ID已存在")

        # 更新模板基本信息
        updated_template = InspirationTemplateDAO.update_template(db, template_id, update_data)

        # 如果提供了factor_relations，全量更新关联
        if factor_relations is not None:
            # 先删除所有旧的关联
            TemplateFactorRelationDAO.delete_relations_by_template_id(db, updated_template.template_id)

            # 创建新的关联
            if factor_relations:
                relations_data = []
                for rel in factor_relations:
                    # 检查因子是否存在
                    factor = FactorDAO.get_factor_by_factor_id(db, rel["factor_id"])
                    if not factor:
                        raise BusinessException(RESOURCE_NOT_FOUND, f"因子ID {rel['factor_id']} 不存在")

                    relations_data.append({
                        "template_id": updated_template.template_id,
                        "factor_id": rel["factor_id"],
                        "factor_usage_type": rel["factor_usage_type"],
                        "sort_order": rel.get("sort_order", 0)
                    })

                TemplateFactorRelationDAO.batch_create_relations(db, relations_data)

        # 返回完整的模板信息
        return InspirationTemplateService.get_template_detail(db, template_id)

    @staticmethod
    def delete_template(db: Session, template_id: int) -> None:
        """删除模板

        :param db: 数据库会话
        :param template_id: 模板主键ID
        :raises BusinessException: 模板不存在时抛出异常
        """
        template = InspirationTemplateDAO.get_template_by_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")

        # 删除关联的因子关系
        TemplateFactorRelationDAO.delete_relations_by_template_id(db, template.template_id)

        # 删除模板
        success = InspirationTemplateDAO.delete_template(db, template_id)
        if not success:
            raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")

    @staticmethod
    def list_templates(
        db: Session,
        strategy_id: Optional[str] = None,
        keyword: Optional[str] = None,
        version: Optional[str] = None,
        min_success_rate: Optional[float] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """分页查询模板列表

        :param db: 数据库会话
        :param strategy_id: 策略ID筛选
        :param keyword: 关键词搜索
        :param version: 版本号筛选
        :param min_success_rate: 最低成功率筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果
        """
        total, templates = InspirationTemplateDAO.list_templates(
            db, strategy_id=strategy_id, keyword=keyword, version=version,
            min_success_rate=min_success_rate, page=page, page_size=page_size
        )
        template_list = []
        for t in templates:
            template_dict = InspirationTemplateService._template_to_dict(t)
            # 查询关联的策略名称
            strategy = StrategyDAO.get_strategy_by_strategy_id(db, t.strategy_id)
            if strategy:
                template_dict["strategy_name"] = strategy.name
            template_list.append(template_dict)

        return {
            "list": template_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }

    @staticmethod
    def _template_to_dict(template: InspirationTemplate) -> Dict[str, Any]:
        """将InspirationTemplate对象转换为字典"""
        return {
            "id": template.id,
            "template_id": template.template_id,
            "strategy_id": template.strategy_id,
            "name": template.name,
            "description": template.description,
            "combination_example": template.combination_example,
            "version": template.version,
            "success_rate": float(template.success_rate) if template.success_rate is not None else 0.0,
            "usage_count": template.usage_count,
            "created_at": template.created_at.isoformat() if template.created_at else "",
            "updated_at": template.updated_at.isoformat() if template.updated_at else "",
        }


class TemplateFactorRelationService:
    """模板-因子关联业务逻辑层"""

    @staticmethod
    def add_relation(db: Session, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """添加模板-因子关联

        :param db: 数据库会话
        :param relation_data: 关联数据
        :return: 创建后的关联信息
        :raises BusinessException: 关联已存在、模板不存在、因子不存在时抛出异常
        """
        template_id = relation_data["template_id"]
        factor_id = relation_data["factor_id"]

        # 检查模板是否存在
        template = InspirationTemplateDAO.get_template_by_template_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, f"模板ID {template_id} 不存在")

        # 检查因子是否存在
        factor = FactorDAO.get_factor_by_factor_id(db, factor_id)
        if not factor:
            raise BusinessException(RESOURCE_NOT_FOUND, f"因子ID {factor_id} 不存在")

        # 检查关联是否已存在
        existing_relations = TemplateFactorRelationDAO.get_relations_by_template_id(db, template_id)
        for rel in existing_relations:
            if rel.factor_id == factor_id:
                raise BusinessException(RESOURCE_ALREADY_EXISTS, "该因子已关联到模板")

        relation = TemplateFactorRelationDAO.create_relation(db, relation_data)
        return TemplateFactorRelationService._relation_to_dict(relation)

    @staticmethod
    def update_relation(db: Session, relation_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新关联信息

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :param update_data: 需要更新的字段
        :return: 更新后的关联信息
        :raises BusinessException: 关联不存在时抛出异常
        """
        relation = TemplateFactorRelationDAO.get_relation_by_id(db, relation_id)
        if not relation:
            raise BusinessException(RESOURCE_NOT_FOUND, "关联不存在")

        updated_relation = TemplateFactorRelationDAO.update_relation(db, relation_id, update_data)
        return TemplateFactorRelationService._relation_to_dict(updated_relation)

    @staticmethod
    def delete_relation(db: Session, relation_id: int) -> None:
        """删除关联

        :param db: 数据库会话
        :param relation_id: 关联主键ID
        :raises BusinessException: 关联不存在时抛出异常
        """
        relation = TemplateFactorRelationDAO.get_relation_by_id(db, relation_id)
        if not relation:
            raise BusinessException(RESOURCE_NOT_FOUND, "关联不存在")

        success = TemplateFactorRelationDAO.delete_relation(db, relation_id)
        if not success:
            raise BusinessException(RESOURCE_NOT_FOUND, "关联不存在")

    @staticmethod
    def get_template_factors(db: Session, template_id: str) -> Dict[str, Any]:
        """获取模板关联的所有因子

        :param db: 数据库会话
        :param template_id: 模板ID
        :return: 因子列表（区分必填和可选）
        :raises BusinessException: 模板不存在时抛出异常
        """
        # 检查模板是否存在
        template = InspirationTemplateDAO.get_template_by_template_id(db, template_id)
        if not template:
            raise BusinessException(RESOURCE_NOT_FOUND, f"模板ID {template_id} 不存在")

        relations = TemplateFactorRelationDAO.get_relations_by_template_id(db, template_id)
        required_factors = []
        optional_factors = []

        for rel in relations:
            factor = FactorDAO.get_factor_by_factor_id(db, rel.factor_id)
            if factor:
                factor_dict = FactorService._factor_to_dict(factor)
                factor_dict["factor_usage_type"] = rel.factor_usage_type
                factor_dict["sort_order"] = rel.sort_order

                if rel.factor_usage_type == 1:
                    required_factors.append(factor_dict)
                else:
                    optional_factors.append(factor_dict)

        return {
            "template_id": template_id,
            "required_factors": required_factors,
            "optional_factors": optional_factors
        }

    @staticmethod
    def _relation_to_dict(relation: TemplateFactorRelation) -> Dict[str, Any]:
        """将TemplateFactorRelation对象转换为字典"""
        return {
            "id": relation.id,
            "template_id": relation.template_id,
            "factor_id": relation.factor_id,
            "factor_usage_type": relation.factor_usage_type,
            "sort_order": relation.sort_order,
            "created_at": relation.created_at.isoformat() if relation.created_at else "",
        }


# 模块级单例，Controller 层直接引用
factor_service = FactorService()
strategy_service = StrategyService()
inspiration_template_service = InspirationTemplateService()
template_factor_relation_service = TemplateFactorRelationService()
