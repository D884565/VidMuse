from typing import List, Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import HOT_REPORT_LIST, CLUSTER_RESULT, FACTOR_LIBRARY, STRATEGY_LIBRARY, STRATEGY_FACTOR_MAPPING
from backend.v1.app.models.inspiration_template import Factor, Strategy
from backend.v1.app.pipeline.services.llm_service import LLMService
import logging
import uuid

logger = logging.getLogger(__name__)


class StrategyGenerator(BaseProcessor):
    """
    抽象策略生成处理器
    为每个聚类簇归纳提炼出对应的创作策略
    """

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取报告、聚类结果和因子库
        2. 对每个聚类簇：
           a. 获取该簇的报告和因子
           b. 调用大模型分析因子组合逻辑，生成抽象策略
           c. 计算策略的历史成功率
           d. 建立策略与适用因子的映射关系
        3. 将策略库和映射关系存入上下文
        """
        reports: List[Dict[str, Any]] = context.get(HOT_REPORT_LIST, [])
        cluster_result: Dict[int, List[int]] = context.get(CLUSTER_RESULT, {})
        factor_library: Dict[int, List[Factor]] = context.get(FACTOR_LIBRARY, {})

        if not reports or not cluster_result or not factor_library:
            logger.warning("缺少必要数据，跳过策略生成")
            context.set(STRATEGY_LIBRARY, {})
            context.set(STRATEGY_FACTOR_MAPPING, {})
            return context

        logger.info(f"开始生成创作策略，簇数量: {len(cluster_result)}")

        strategy_library: Dict[str, Strategy] = {}
        strategy_factor_mapping: Dict[str, List[str]] = {}

        for cluster_id, report_indices in cluster_result.items():
            logger.info(f"处理簇 {cluster_id} 策略生成")

            # 获取该簇的报告和因子
            cluster_reports = [reports[i] for i in report_indices]
            cluster_factors = factor_library.get(cluster_id, [])

            if not cluster_factors:
                logger.warning(f"簇 {cluster_id} 没有可用因子，跳过策略生成")
                continue

            try:
                # 调用大模型生成策略
                strategy_data = self.llm_service.generate_strategy(
                    cluster_reports, cluster_factors
                )

                if not strategy_data:
                    logger.warning(f"簇 {cluster_id} 生成策略为空，跳过")
                    continue

                # 生成唯一策略ID
                strategy_id = strategy_data.get("strategy_id", f"s_{uuid.uuid4().hex[:8]}")

                # 计算策略成功率
                success_rate = self.llm_service.calculate_strategy_success_rate(
                    cluster_reports, strategy_data
                )
                strategy_data["success_rate"] = success_rate

                # 转换为Strategy模型
                strategy = Strategy(
                    strategy_id=strategy_id,
                    **{k: v for k, v in strategy_data.items() if k != "strategy_id"}
                )

                # 建立策略与因子的映射：找出适用的因子
                applicable_factor_ids = []
                for factor in cluster_factors:
                    if factor.factor_type in strategy.required_factor_types + strategy.optional_factor_types:
                        applicable_factor_ids.append(factor.factor_id)

                # 存入结果
                strategy_library[strategy_id] = strategy
                strategy_factor_mapping[strategy_id] = applicable_factor_ids

                logger.info(f"簇 {cluster_id} 生成策略: {strategy.name}, ID: {strategy_id}, 成功率: {success_rate:.2f}")

            except Exception as e:
                logger.error(f"处理簇 {cluster_id} 生成策略失败: {str(e)}", exc_info=True)
                continue

        logger.info(f"策略生成完成，总策略数量: {len(strategy_library)}")

        # 存入上下文
        context.set(STRATEGY_LIBRARY, strategy_library)
        context.set(STRATEGY_FACTOR_MAPPING, strategy_factor_mapping)

        return context
