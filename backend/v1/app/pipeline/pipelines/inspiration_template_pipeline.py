from backend.v1.app.pipeline.base.pipeline import BasePipeline
from backend.v1.app.pipeline.processors import (
    HotReportFetchProcessor,
    EmbeddingClusteringProcessor,
    CommonFactorExtractor,
    StrategyGenerator,
    TemplateAssembler
)


class InspirationTemplatePipeline(BasePipeline):
    """
    灵感模板提炼流水线
    从爆款视频报告中提炼可用于AI生产的结构化灵感模板

    处理流程：
    1. 批量读取爆款报告和对应向量
    2. 基于向量相似度聚类
    3. 提取各簇共性因子
    4. 生成抽象创作策略
    5. 组装为完整灵感模板
    """

    def __init__(self,
                 min_hot_score: int = 80,
                 cluster_eps: float = 0.2,
                 cluster_min_samples: int = 3,
                 limit: int = None,
                 enable_persistence: bool = True):
        """
        初始化灵感模板流水线

        :param min_hot_score: 最小爆款分数阈值，默认80分
        :param cluster_eps: DBSCAN聚类邻域阈值，默认0.2（余弦距离）
        :param cluster_min_samples: 聚类最小样本数，默认3
        :param limit: 最大处理报告数量，默认不限制
        :param enable_persistence: 是否开启持久化
        """
        processors = [
            HotReportFetchProcessor(min_hot_score=min_hot_score, limit=limit),
            EmbeddingClusteringProcessor(eps=cluster_eps, min_samples=cluster_min_samples),
            CommonFactorExtractor(),
            StrategyGenerator(),
            TemplateAssembler()
        ]

        super().__init__(
            processors=processors,
            enable_persistence=enable_persistence,
            pipeline_type="INSPIRATION_TEMPLATE"
        )
