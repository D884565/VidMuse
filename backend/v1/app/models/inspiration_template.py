"""灵感模板模块ORM模型"""
import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, func, JSON, DECIMAL, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from backend.store.database.async_database import Base


class Factor(Base):
    """创作因子表 ORM 模型"""
    __tablename__ = "factors"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    factor_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="全局唯一因子ID")
    factor_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="因子类型：content_structure/product_expression/user_operation")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="因子名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="因子详细描述")
    applicable_scenarios: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="适用场景列表")
    data_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="因子数据结构定义")
    example: Mapped[dict | list | None] = mapped_column(JSON, nullable=True, comment="因子示例数据")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="标签列表")
    popularity: Mapped[float] = mapped_column(DECIMAL(4, 3), nullable=False, default=0.0, comment="流行度，0-1之间")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数统计")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="是否删除：0-未删除，1-已删除")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Strategy(Base):
    """创作策略表 ORM 模型"""
    __tablename__ = "strategies"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    strategy_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="全局唯一策略ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="策略名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="策略详细描述")
    applicable_scenarios: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="适用场景列表")
    core_logic: Mapped[str | None] = mapped_column(Text, nullable=True, comment="核心创作逻辑描述")
    required_factor_types: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="必填因子类型列表")
    optional_factor_types: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="可选因子类型列表")
    combination_rules: Mapped[str | None] = mapped_column(Text, nullable=True, comment="因子组合规则描述")
    success_rate: Mapped[float] = mapped_column(DECIMAL(4, 3), nullable=False, default=0.0, comment="历史爆款成功率，0-1之间")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="标签列表")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数统计")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="是否删除：0-未删除，1-已删除")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class InspirationTemplate(Base):
    """灵感模板表 ORM 模型"""
    __tablename__ = "inspiration_templates"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    template_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="全局唯一模板ID")
    strategy_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="关联的策略ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="模板描述")
    combination_example: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="完整组合示例")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0", comment="版本号")
    success_rate: Mapped[float] = mapped_column(DECIMAL(4, 3), nullable=False, default=0.0, comment="模板成功率，0-1之间")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数统计")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="是否删除：0-未删除，1-已删除")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class TemplateFactorRelation(Base):
    """模板-因子关联表 ORM 模型"""
    __tablename__ = "template_factor_relations"

    # 主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    template_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="模板ID")
    factor_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="因子ID")
    factor_usage_type: Mapped[int] = mapped_column(Integer, nullable=False, comment="因子使用类型：1-必填，2-可选")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序权重")

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
