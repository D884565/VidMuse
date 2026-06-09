from typing import List, Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import FACTOR_INDEX, STRATEGY_LIBRARY, STRATEGY_FACTOR_MAPPING
from backend.v1.app.models.inspiration_template import Factor, Strategy
from backend.v1.app.pipeline.services.llm_service import LLMService
import logging
import uuid

logger = logging.getLogger(__name__)


class VideoStrategyGenerator(BaseProcessor):
    """
    视频策略生成处理器
    从video聚类结果中生成创作策略，与之前任务脚本逻辑完全一致
    """

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取video聚类结果和已生成的因子库
        2. 对每个video簇生成创作策略
        3. 建立策略与因子的映射关系
        """
        video_clusters: Dict[int, List[Dict[str, Any]]] = context.get("VIDEO_CLUSTERS", {})
        factor_index: Dict[str, Factor] = context.get(FACTOR_INDEX, {})
        all_factors = list(factor_index.values())

        if not video_clusters:
            logger.warning("没有video聚类结果，跳过策略生成")
            context.set(STRATEGY_LIBRARY, {})
            context.set(STRATEGY_FACTOR_MAPPING, {})
            return context

        logger.info(f"开始从video簇生成策略，簇数量: {len(video_clusters)}")

        strategy_library: Dict[str, Strategy] = {}
        strategy_factor_mapping: Dict[str, List[str]] = {}
        strategy_counter = 1

        for cluster_id, docs in video_clusters.items():
            logger.info(f"处理video簇 {cluster_id}, 样本数: {len(docs)}")

            # 准备分析数据
            cluster_reports = []
            for doc in docs:
                # 截断文档避免token过多
                content = doc["document"][:1500] + "..." if len(doc["document"]) > 1500 else doc["document"]
                cluster_reports.append({
                    "content": content,
                    "hot_score": 85,  # 默认爆款分数
                    "metadata": doc["metadata"]
                })

            try:
                # 第一步：提取该簇的因子（如果没有则用全局因子）
                factors_data = self.llm_service.extract_common_factors(cluster_reports)
                cluster_factors = []

                if factors_data:
                    # 转换为Factor模型，视频簇的因子也加入全局因子库
                    for factor_data in factors_data:
                        factor_id = f"f_v{cluster_id}_{len(all_factors) + 1}"
                        try:
                            factor = Factor(
                                factor_id=factor_id,
                                factor_type=factor_data.get("factor_type", "content_structure"),
                                name=factor_data.get("name", f"因子_{factor_id}"),
                                description=factor_data.get("description", f"从video簇{cluster_id}提取的共性因子"),
                                applicable_scenarios=factor_data.get("applicable_scenarios", ["通用"]),
                                data_schema=factor_data.get("data_schema", {}),
                                example=factor_data.get("example", {}),
                                tags=factor_data.get("tags", []) + [f"video_cluster_{cluster_id}"],
                                popularity=factor_data.get("popularity", 0.8),
                                usage_count=0
                            )
                            cluster_factors.append(factor)
                            factor_index[factor_id] = factor
                            all_factors.append(factor)
                        except Exception as e:
                            logger.error(f"构建video因子失败: {str(e)}", exc_info=True)
                            continue

                    logger.info(f"簇 {cluster_id} 额外提取到 {len(cluster_factors)} 个专属因子")

                # 第二步：生成策略
                if not cluster_factors:
                    # 如果没有簇专属因子，使用全局因子
                    cluster_factors = all_factors[:10]  # 取前10个因子供策略生成使用

                strategy_data = self.llm_service.generate_strategy(cluster_reports, cluster_factors)
                if not strategy_data:
                    logger.warning(f"簇 {cluster_id} 未生成策略，跳过")
                    continue

                # 计算成功率
                success_rate = min(0.95, 0.7 + len(docs) / 20)
                strategy_data["success_rate"] = success_rate

                # 生成连续的策略ID，和任务脚本保持一致
                strategy_id = f"s_{strategy_counter:04d}"
                strategy_counter += 1

                # 转换为Strategy模型
                strategy = Strategy(
                    strategy_id=strategy_id,
                    name=strategy_data.get("name", f"策略_{strategy_id}"),
                    description=strategy_data.get("description", f"从video簇{cluster_id}生成的创作策略"),
                    applicable_scenarios=strategy_data.get("applicable_scenarios", ["通用"]),
                    core_logic=strategy_data.get("core_logic", ""),
                    required_factor_types=strategy_data.get("required_factor_types", ["content_structure"]),
                    optional_factor_types=strategy_data.get("optional_factor_types", []),
                    combination_rules=strategy_data.get("combination_rules", ""),
                    success_rate=success_rate,
                    tags=strategy_data.get("tags", []) + [f"video_cluster_{cluster_id}"],
                    usage_count=0
                )

                # 建立策略与因子的映射
                applicable_factor_ids = []
                # 匹配必填因子类型
                for factor_type in strategy.required_factor_types:
                    type_factors = [f for f in all_factors if f.factor_type == factor_type]
                    if type_factors:
                        applicable_factor_ids.append(type_factors[0].factor_id)
                # 匹配可选因子类型
                for factor_type in strategy.optional_factor_types[:3]:  # 最多3个可选
                    type_factors = [f for f in all_factors if f.factor_type == factor_type]
                    if type_factors:
                        factor_id = type_factors[0].factor_id
                        if factor_id not in applicable_factor_ids:
                            applicable_factor_ids.append(factor_id)

                # 存入结果
                strategy_library[strategy_id] = strategy
                strategy_factor_mapping[strategy_id] = applicable_factor_ids

                logger.info(f"簇 {cluster_id} 生成策略: {strategy.name}, ID: {strategy_id}, 成功率: {success_rate:.2f}")

            except Exception as e:
                logger.error(f"处理簇 {cluster_id} 生成策略失败: {str(e)}", exc_info=True)
                continue

        logger.info(f"策略生成完成，总策略数量: {len(strategy_library)}")

        # 更新上下文的因子索引（可能新增了video簇的因子）
        context.set(FACTOR_INDEX, factor_index)
        # 存入策略结果
        context.set(STRATEGY_LIBRARY, strategy_library)
        context.set(STRATEGY_FACTOR_MAPPING, strategy_factor_mapping)

        return context
