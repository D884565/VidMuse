from typing import List, Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import FACTOR_INDEX, STRATEGY_LIBRARY, STRATEGY_FACTOR_MAPPING, INSPIRATION_TEMPLATES
from backend.v1.app.models.inspiration_template import Factor, Strategy, InspirationTemplate
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class TemplateAssembler(BaseProcessor):
    """
    灵感模板组装处理器
    将策略与适用因子绑定，生成完整的结构化灵感模板
    """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取因子索引、策略库和策略-因子映射
        2. 对每个策略：
           a. 根据策略的必填/可选因子类型，从适用因子中筛选分类
           b. 生成组合示例
           c. 组装为完整的灵感模板
        3. 将模板列表存入上下文
        """
        factor_index: Dict[str, Factor] = context.get(FACTOR_INDEX, {})
        strategy_library: Dict[str, Strategy] = context.get(STRATEGY_LIBRARY, {})
        strategy_factor_mapping: Dict[str, List[str]] = context.get(STRATEGY_FACTOR_MAPPING, {})

        if not factor_index or not strategy_library:
            logger.warning("缺少因子或策略数据，跳过模板组装")
            context.set(INSPIRATION_TEMPLATES, [])
            return context

        logger.info(f"开始组装灵感模板，策略数量: {len(strategy_library)}")

        templates: List[InspirationTemplate] = []

        for strategy_id, strategy in strategy_library.items():
            logger.info(f"组装策略 {strategy_id}: {strategy.name}")

            # 获取该策略的适用因子ID列表
            applicable_factor_ids = strategy_factor_mapping.get(strategy_id, [])

            # 如果没有映射关系，根据因子类型自动匹配
            if not applicable_factor_ids:
                logger.info(f"策略 {strategy_id} 没有预映射的因子，将根据类型自动匹配")
                all_factors = list(factor_index.values())
                # 匹配所有符合必填和可选类型的因子
                applicable_types = strategy.required_factor_types + strategy.optional_factor_types
                applicable_factors = [f for f in all_factors if f.factor_type in applicable_types]
            else:
                # 从索引中获取因子实例
                applicable_factors: List[Factor] = []
                for factor_id in applicable_factor_ids:
                    factor = factor_index.get(factor_id)
                    if factor:
                        applicable_factors.append(factor)
                    else:
                        logger.warning(f"因子 {factor_id} 不存在于索引中，已忽略")

            # 分为必填和可选因子
            required_factors = []
            optional_factors = []
            for factor in applicable_factors:
                if factor.factor_type in strategy.required_factor_types:
                    required_factors.append(factor)
                elif factor.factor_type in strategy.optional_factor_types:
                    optional_factors.append(factor)

            # 生成组合示例
            combination_example = self._generate_combination_example(
                strategy, required_factors, optional_factors
            )

            # 组装模板
            template = InspirationTemplate(
                template_id=f"t_{uuid.uuid4().hex[:8]}",
                strategy_id=strategy.strategy_id,
                name=strategy.name,
                description=strategy.description,
                combination_example=combination_example,
                version="v1.0",
                success_rate=strategy.success_rate,
                usage_count=0
            )
            # 临时存储关联的因子，用于后续持久化
            template.required_factors = required_factors
            template.optional_factors = optional_factors

            templates.append(template)
            logger.info(f"生成模板: {template.template_id}, 必填因子: {len(required_factors)}, 可选因子: {len(optional_factors)}")

        logger.info(f"模板组装完成，总模板数量: {len(templates)}")

        # 存入上下文
        context.set(INSPIRATION_TEMPLATES, templates)

        return context

    def _generate_combination_example(self, strategy: Strategy,
                                      required_factors: List[Factor],
                                      optional_factors: List[Factor]) -> Dict[str, Any]:
        """
        生成策略与因子的组合示例
        """
        example = {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.name,
            "core_logic": strategy.core_logic,
            "flow": [],
            "factors": {}
        }

        # 按核心逻辑顺序排列因子，支持多种分隔符
        import re
        # 支持的分隔符：→, ->, =>, 换行, 分号, 顿号
        logic_steps = [
            step.strip()
            for step in re.split(r'→|->|=>|\n|;|、', strategy.core_logic)
            if step.strip()  # 过滤空步骤
        ]

        # 所有可用因子（必填 + 可选）
        all_factors = required_factors + optional_factors

        # 为每个步骤匹配合适的因子
        for step in logic_steps:
            step_lower = step.lower()
            matched_factor = None

            # 优先在必填因子中匹配
            for factor in all_factors:
                factor_name = factor.name.lower()
                factor_tags = [tag.lower() for tag in factor.tags]
                factor_type = factor.factor_type.lower()

                # 模糊匹配：步骤关键词在因子名称、标签或类型中
                if (step_lower in factor_name or
                    any(step_lower in tag for tag in factor_tags) or
                    step_lower in factor_type):
                    matched_factor = factor
                    break

            if matched_factor:
                example["flow"].append({
                    "step": step,
                    "factor_id": matched_factor.factor_id,
                    "factor_name": matched_factor.name,
                    "example": matched_factor.example
                })
                example["factors"][matched_factor.factor_id] = matched_factor.example
            else:
                example["flow"].append({
                    "step": step,
                    "factor_id": None,
                    "description": "可自由配置"
                })

        return example
