"""灵感模板模块 Pydantic 模型

定义灵感模板模块的请求体和响应体结构，用于 FastAPI 的参数校验和序列化。
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== 因子相关模型 ====================

class FactorBase(BaseModel):
    """因子基础模型"""
    factor_id: str = Field(description="全局唯一因子ID")
    factor_type: str = Field(description="因子类型：content_structure/product_expression/user_operation")
    name: str = Field(description="因子名称")
    description: Optional[str] = Field(None, description="因子详细描述")
    applicable_scenarios: Optional[List[str]] = Field(None, description="适用场景列表")
    data_schema: Optional[Dict[str, Any]] = Field(None, description="因子数据结构定义")
    example: Optional[Any] = Field(None, description="因子示例数据")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    popularity: float = Field(default=0.0, ge=0, le=1, description="流行度，0-1之间")


class FactorCreateRequest(FactorBase):
    """创建因子请求体"""
    pass


class FactorUpdateRequest(BaseModel):
    """更新因子请求体"""
    factor_type: Optional[str] = Field(None, description="因子类型")
    name: Optional[str] = Field(None, description="因子名称")
    description: Optional[str] = Field(None, description="因子详细描述")
    applicable_scenarios: Optional[List[str]] = Field(None, description="适用场景列表")
    data_schema: Optional[Dict[str, Any]] = Field(None, description="因子数据结构定义")
    example: Optional[Any] = Field(None, description="因子示例数据")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    popularity: Optional[float] = Field(None, ge=0, le=1, description="流行度，0-1之间")


class FactorResponse(FactorBase):
    """因子响应体"""
    id: int = Field(description="主键ID")
    usage_count: int = Field(description="使用次数统计")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


# ==================== 策略相关模型 ====================

class StrategyBase(BaseModel):
    """策略基础模型"""
    strategy_id: str = Field(description="全局唯一策略ID")
    name: str = Field(description="策略名称")
    description: Optional[str] = Field(None, description="策略详细描述")
    applicable_scenarios: Optional[List[str]] = Field(None, description="适用场景列表")
    core_logic: Optional[str] = Field(None, description="核心创作逻辑描述")
    required_factor_types: Optional[List[str]] = Field(None, description="必填因子类型列表")
    optional_factor_types: Optional[List[str]] = Field(None, description="可选因子类型列表")
    combination_rules: Optional[str] = Field(None, description="因子组合规则描述")
    success_rate: float = Field(default=0.0, ge=0, le=1, description="历史爆款成功率，0-1之间")
    tags: Optional[List[str]] = Field(None, description="标签列表")


class StrategyCreateRequest(StrategyBase):
    """创建策略请求体"""
    pass


class StrategyUpdateRequest(BaseModel):
    """更新策略请求体"""
    name: Optional[str] = Field(None, description="策略名称")
    description: Optional[str] = Field(None, description="策略详细描述")
    applicable_scenarios: Optional[List[str]] = Field(None, description="适用场景列表")
    core_logic: Optional[str] = Field(None, description="核心创作逻辑描述")
    required_factor_types: Optional[List[str]] = Field(None, description="必填因子类型列表")
    optional_factor_types: Optional[List[str]] = Field(None, description="可选因子类型列表")
    combination_rules: Optional[str] = Field(None, description="因子组合规则描述")
    success_rate: Optional[float] = Field(None, ge=0, le=1, description="历史爆款成功率，0-1之间")
    tags: Optional[List[str]] = Field(None, description="标签列表")


class StrategyResponse(StrategyBase):
    """策略响应体"""
    id: int = Field(description="主键ID")
    usage_count: int = Field(description="使用次数统计")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


# ==================== 灵感模板相关模型 ====================

class InspirationTemplateBase(BaseModel):
    """灵感模板基础模型"""
    template_id: str = Field(description="全局唯一模板ID")
    strategy_id: str = Field(description="关联的策略ID")
    name: str = Field(description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    combination_example: Optional[Dict[str, Any]] = Field(None, description="完整组合示例")
    version: str = Field(default="v1.0", description="版本号")
    success_rate: float = Field(default=0.0, ge=0, le=1, description="模板成功率，0-1之间")


class InspirationTemplateCreateRequest(InspirationTemplateBase):
    """创建灵感模板请求体"""
    factor_relations: Optional[List[Dict[str, Any]]] = Field(None, description="关联的因子列表，包含factor_id和factor_usage_type")


class InspirationTemplateUpdateRequest(BaseModel):
    """更新灵感模板请求体"""
    strategy_id: Optional[str] = Field(None, description="关联的策略ID")
    name: Optional[str] = Field(None, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    combination_example: Optional[Dict[str, Any]] = Field(None, description="完整组合示例")
    version: Optional[str] = Field(None, description="版本号")
    success_rate: Optional[float] = Field(None, ge=0, le=1, description="模板成功率，0-1之间")
    factor_relations: Optional[List[Dict[str, Any]]] = Field(None, description="关联的因子列表，包含factor_id和factor_usage_type")


class InspirationTemplateResponse(InspirationTemplateBase):
    """灵感模板响应体"""
    id: int = Field(description="主键ID")
    usage_count: int = Field(description="使用次数统计")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    strategy: Optional[StrategyResponse] = Field(None, description="关联的策略信息")
    required_factors: Optional[List[FactorResponse]] = Field(None, description="必填因子列表")
    optional_factors: Optional[List[FactorResponse]] = Field(None, description="可选因子列表")

    model_config = {"from_attributes": True}


# ==================== 模板-因子关联相关模型 ====================

class TemplateFactorRelationBase(BaseModel):
    """模板-因子关联基础模型"""
    template_id: str = Field(description="模板ID")
    factor_id: str = Field(description="因子ID")
    factor_usage_type: int = Field(description="因子使用类型：1-必填，2-可选")
    sort_order: int = Field(default=0, description="排序权重")


class TemplateFactorRelationCreateRequest(TemplateFactorRelationBase):
    """创建模板-因子关联请求体"""
    pass


class TemplateFactorRelationUpdateRequest(BaseModel):
    """更新模板-因子关联请求体"""
    factor_usage_type: Optional[int] = Field(None, description="因子使用类型：1-必填，2-可选")
    sort_order: Optional[int] = Field(None, description="排序权重")


class TemplateFactorRelationResponse(TemplateFactorRelationBase):
    """模板-因子关联响应体"""
    id: int = Field(description="主键ID")
    created_at: datetime = Field(description="创建时间")
    factor: Optional[FactorResponse] = Field(None, description="关联的因子信息")

    model_config = {"from_attributes": True}
