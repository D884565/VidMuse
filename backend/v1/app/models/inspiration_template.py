from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime


class Factor(BaseModel):
    """
    因子模型：最细粒度的可复用创作单元
    """
    factor_id: str = Field(description="全局唯一因子ID")
    factor_type: str = Field(description="因子类型：content_structure/product_expression/user_operation等")
    name: str = Field(description="因子名称")
    description: str = Field(description="因子详细描述")
    applicable_scenarios: List[str] = Field(description="适用场景列表")
    data_schema: Dict[str, Any] = Field(description="因子数据结构定义")
    example: Any = Field(description="因子示例数据")
    tags: List[str] = Field(default_factory=list, description="标签，用于检索")
    popularity: float = Field(ge=0, le=1, description="流行度，基于出现频率计算，0-1之间")


class Strategy(BaseModel):
    """
    策略模型：抽象的创作方法论
    """
    strategy_id: str = Field(description="全局唯一策略ID")
    name: str = Field(description="策略名称")
    description: str = Field(description="策略详细描述")
    applicable_scenarios: List[str] = Field(description="适用场景列表")
    core_logic: str = Field(description="核心创作逻辑描述")
    required_factor_types: List[str] = Field(description="必填因子类型列表")
    optional_factor_types: List[str] = Field(default_factory=list, description="可选因子类型列表")
    combination_rules: str = Field(description="因子组合规则描述")
    success_rate: float = Field(ge=0, le=1, description="该策略的历史爆款成功率，0-1之间")
    tags: List[str] = Field(default_factory=list, description="标签")


class InspirationTemplate(BaseModel):
    """
    灵感模板模型：策略与因子的组合
    """
    template_id: str = Field(description="全局唯一模板ID")
    strategy: Strategy = Field(description="关联的创作策略")
    required_factors: List[Factor] = Field(description="必填因子实例列表")
    optional_factors: List[Factor] = Field(default_factory=list, description="可选因子实例列表")
    combination_example: Dict[str, Any] = Field(description="完整组合示例")
    version: str = Field(default="v1.0", description="版本号")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
