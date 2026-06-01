from typing import List, Dict, Any
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import HOT_REPORT_LIST, CLUSTER_RESULT, FACTOR_LIBRARY, FACTOR_INDEX
from backend.v1.app.models.inspiration_template import Factor
from backend.v1.app.services.llm_service import LLMService
import logging
import uuid

logger = logging.getLogger(__name__)


class CommonFactorExtractor(BaseProcessor):
    """
    共性因子提取处理器
    从每个聚类簇的报告中提取可复用的细粒度因子
    """

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取报告列表和聚类结果
        2. 对每个聚类簇：
           a. 提取该簇的所有报告
           b. 调用大模型分析共性，提取因子
           c. 为每个因子生成唯一ID
        3. 构建因子库和全局索引
        4. 将结果存入上下文
        """
        reports: List[Dict[str, Any]] = context.get(HOT_REPORT_LIST, [])
        cluster_result: Dict[int, List[int]] = context.get(CLUSTER_RESULT, {})

        if not reports or not cluster_result:
            logger.warning("报告列表或聚类结果为空，跳过因子提取")
            context.set(FACTOR_LIBRARY, {})
            context.set(FACTOR_INDEX, {})
            return context

        logger.info(f"开始提取共性因子，簇数量: {len(cluster_result)}")

        factor_library: Dict[int, List[Factor]] = {}
        factor_index: Dict[str, Factor] = {}

        for cluster_id, report_indices in cluster_result.items():
            logger.info(f"处理簇 {cluster_id}, 报告数量: {len(report_indices)}")

            # 获取该簇的所有报告数据
            cluster_reports = [reports[i] for i in report_indices]

            # 调用大模型提取共性因子
            try:
                factors_data = self.llm_service.extract_common_factors(cluster_reports)

                # 转换为Factor模型并生成唯一ID
                factors = []
                for factor_data in factors_data:
                    # 生成唯一因子ID
                    factor_id = factor_data.get("factor_id", f"f_{uuid.uuid4().hex[:8]}")
                    try:
                        factor = Factor(
                            factor_id=factor_id,
                            **{k: v for k, v in factor_data.items() if k != "factor_id"}
                        )
                        factors.append(factor)
                        factor_index[factor_id] = factor
                    except Exception as e:
                        logger.error(f"解析因子数据失败: {str(e)}, 因子数据: {factor_data}")
                        continue

                factor_library[cluster_id] = factors
                logger.info(f"簇 {cluster_id} 提取因子数量: {len(factors)}")

            except Exception as e:
                logger.error(f"处理簇 {cluster_id} 提取因子失败: {str(e)}", exc_info=True)
                factor_library[cluster_id] = []

        logger.info(f"因子提取完成，总因子数量: {len(factor_index)}")

        # 存入上下文
        context.set(FACTOR_LIBRARY, factor_library)
        context.set(FACTOR_INDEX, factor_index)

        return context
