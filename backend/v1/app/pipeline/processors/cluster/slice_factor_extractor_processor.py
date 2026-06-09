from typing import List, Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import FACTOR_LIBRARY, FACTOR_INDEX
from backend.v1.app.models.inspiration_template import Factor
from backend.v1.app.pipeline.services.llm_service import LLMService
import logging
import uuid

logger = logging.getLogger(__name__)


class SliceFactorExtractor(BaseProcessor):
    """
    片段因子提取处理器
    从slice聚类结果中提取共性因子，与之前任务脚本逻辑完全一致
    """

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取slice聚类结果
        2. 对每个slice簇提取共性因子
        3. 构建全局因子库和索引
        """
        slice_clusters: Dict[int, List[Dict[str, Any]]] = context.get("SLICE_CLUSTERS", {})

        if not slice_clusters:
            logger.warning("没有slice聚类结果，跳过因子提取")
            context.set(FACTOR_LIBRARY, {})
            context.set(FACTOR_INDEX, {})
            return context

        logger.info(f"开始从slice簇提取因子，簇数量: {len(slice_clusters)}")

        factor_library: Dict[int, List[Factor]] = {}
        factor_index: Dict[str, Factor] = {}
        factor_counter = 1

        for cluster_id, docs in slice_clusters.items():
            logger.info(f"处理slice簇 {cluster_id}, 样本数: {len(docs)}")

            # 准备分析数据
            cluster_reports = []
            for doc in docs:
                # 截断文档避免token过多
                content = doc["document"][:1000] + "..." if len(doc["document"]) > 1000 else doc["document"]
                cluster_reports.append({
                    "content": content,
                    "hot_score": 85,  # 默认爆款分数
                    "metadata": doc["metadata"]
                })

            try:
                # 调用LLM提取共性因子
                factors_data = self.llm_service.extract_common_factors(cluster_reports)

                if not factors_data:
                    logger.warning(f"簇 {cluster_id} 未提取到因子，跳过")
                    continue

                # 转换为Factor模型
                cluster_factors = []
                for factor_data in factors_data:
                    # 生成连续的因子ID，和任务脚本保持一致
                    factor_id = f"f_{factor_counter:04d}"
                    factor_counter += 1

                    try:
                        factor = Factor(
                            factor_id=factor_id,
                            factor_type=factor_data.get("factor_type", "content_structure"),
                            name=factor_data.get("name", f"因子_{factor_id}"),
                            description=factor_data.get("description", f"从slice簇{cluster_id}提取的共性因子"),
                            applicable_scenarios=factor_data.get("applicable_scenarios", ["通用"]),
                            data_schema=factor_data.get("data_schema", {}),
                            example=factor_data.get("example", {}),
                            tags=factor_data.get("tags", []) + [f"slice_cluster_{cluster_id}"],
                            popularity=factor_data.get("popularity", 0.8),
                            usage_count=0
                        )
                        cluster_factors.append(factor)
                        factor_index[factor_id] = factor
                    except Exception as e:
                        logger.error(f"构建因子失败: {str(e)}", exc_info=True)
                        continue

                factor_library[cluster_id] = cluster_factors
                logger.info(f"簇 {cluster_id} 成功提取 {len(cluster_factors)} 个因子")

            except Exception as e:
                logger.error(f"处理簇 {cluster_id} 提取因子失败: {str(e)}", exc_info=True)
                continue

        logger.info(f"因子提取完成，总因子数量: {len(factor_index)}")

        # 存入上下文
        context.set(FACTOR_LIBRARY, factor_library)
        context.set(FACTOR_INDEX, factor_index)

        return context
