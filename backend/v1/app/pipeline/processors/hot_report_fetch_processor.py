from typing import Dict, Any, Tuple, List, Optional
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import HOT_REPORT_LIST, REPORT_EMBEDDINGS
from backend.store.collection.video_knowledge_dao import VideoKnowledgeDAO
from backend.v1.app.dao.video_report_dao import VideoReportDAO
from backend.store.database.sync_database import get_db
import logging

logger = logging.getLogger(__name__)


class HotReportFetchProcessor(BaseProcessor):
    """
    爆款报告批量读取处理器
    从数据库拉取符合条件的爆款视频结构化解析报告及对应预生成向量
    """

    def __init__(self, min_hot_score: int = 80, limit: Optional[int] = None):
        """
        初始化处理器

        :param min_hot_score: 最小爆款分数阈值，默认80分
        :param limit: 最大返回报告数量，默认不限制
        """
        self.min_hot_score = min_hot_score
        self.limit = limit
        self.video_knowledge_dao = VideoKnowledgeDAO()

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取过滤参数
        2. 调用DAO层查询爆款报告元数据
        3. 根据视频ID批量查询对应向量
        4. 将结果存入上下文

        支持的过滤参数（从上下文获取）：
        - category: 商品品类
        - min_hot_score: 最小爆款分数(0-100)，覆盖初始化参数
        - start_time: 开始时间(UTC时间戳)
        - end_time: 结束时间(UTC时间戳)
        - limit: 最大返回数量，覆盖初始化参数
        """
        # 获取过滤参数
        filter_params: Dict[str, Any] = context.data.copy()

        # 合并默认参数
        if "min_hot_score" not in filter_params:
            filter_params["min_hot_score"] = self.min_hot_score
        if "limit" not in filter_params and self.limit is not None:
            filter_params["limit"] = self.limit

        logger.info(f"开始拉取爆款报告，过滤参数: {filter_params}")

        # 查询关系型数据库获取结构化报告
        db = next(get_db())
        try:
            # 1. 获取爆款报告元数据
            reports = VideoReportDAO.get_hot_reports(
                db, **filter_params
            )

            if not reports:
                logger.warning("未找到符合条件的爆款报告")
                context.set(HOT_REPORT_LIST, [])
                context.set(REPORT_EMBEDDINGS, [])
                return context

            logger.info(f"找到符合条件的报告数量: {len(reports)}")

            # 2. 提取视频ID列表
            video_ids = [report["video_id"] for report in reports]

            # 3. 批量查询向量数据库获取对应向量
            embeddings = []
            for video_id in video_ids:
                # 查询该视频的向量（每个视频对应一个整体向量）
                try:
                    # 使用空查询向量，只按video_id过滤，获取该视频的所有向量
                    result = self.video_knowledge_dao.query_by_video_id(
                        video_id=video_id,
                        query_embeddings=[[]],  # 空向量，不进行相似度匹配
                        n_results=1  # 每个视频只需要一个整体向量
                    )

                    if result and result.get("embeddings") and len(result["embeddings"]) > 0:
                        embeddings.append(result["embeddings"][0])
                    else:
                        logger.warning(f"视频 {video_id} 未找到对应向量，跳过该报告")
                        # 移除对应的报告
                        reports = [r for r in reports if r["video_id"] != video_id]

                except Exception as e:
                    logger.error(f"查询视频 {video_id} 向量失败: {str(e)}", exc_info=True)
                    reports = [r for r in reports if r["video_id"] != video_id]
                    continue

            logger.info(f"成功拉取有效报告数量: {len(reports)}, 对应向量数量: {len(embeddings)}")

            # 存入上下文
            context.set(HOT_REPORT_LIST, reports)
            context.set(REPORT_EMBEDDINGS, embeddings)

            return context

        finally:
            db.close()
