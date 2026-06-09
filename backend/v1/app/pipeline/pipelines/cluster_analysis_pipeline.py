from backend.v1.app.pipeline.base.pipeline import BasePipeline
from backend.v1.app.pipeline.processors.cluster import (
    VectorFetchProcessor,
    DualClusteringProcessor,
    SliceFactorExtractor,
    VideoStrategyGenerator,
    TemplateAssembler,
    TemplatePersistenceProcessor
)


class ClusterAnalysisPipeline(BasePipeline):
    """
    聚类分析完整流水线
    与之前任务脚本逻辑完全一致，直接从向量库拉取数据完成全流程分析

    处理流程：
    1. 从向量库拉取slice和video两个集合的原始数据
    2. 分别对两个集合进行独立聚类
    3. 分析slice聚类簇，提取共性创作因子
    4. 分析video聚类簇，生成抽象创作策略
    5. 将策略与因子组合，组装为完整灵感模板
    6. 自动持久化到MySQL数据库
    """

    def __init__(self,
                 max_vectors: int = 800,
                 cluster_eps: float = 0.2,
                 cluster_min_samples: int = 3,
                 max_samples_per_cluster: int = 5,
                 auto_save_to_db: bool = True,
                 enable_persistence: bool = True):
        """
        初始化聚类分析流水线

        :param max_vectors: 最大处理向量数量，默认800
        :param cluster_eps: DBSCAN聚类邻域阈值，默认0.2（余弦距离）
        :param cluster_min_samples: 聚类最小样本数，默认3
        :param max_samples_per_cluster: 每个簇最多分析的样本数，默认5
        :param auto_save_to_db: 是否自动将结果保存到数据库
        :param enable_persistence: 是否开启执行状态持久化（断点续跑）
        """
        processors = [
            # 1. 从向量库拉取原始数据
            VectorFetchProcessor(
                collection_type="both",
                max_vectors=max_vectors
            ),
            # 2. 双集合独立聚类
            DualClusteringProcessor(
                cluster_eps=cluster_eps,
                cluster_min_samples=cluster_min_samples,
                max_samples_per_cluster=max_samples_per_cluster
            ),
            # 3. 从slice簇提取因子
            SliceFactorExtractor(),
            # 4. 从video簇生成策略（复用因子）
            VideoStrategyGenerator(),
            # 5. 组装完整灵感模板
            TemplateAssembler()
        ]

        # 添加持久化处理器
        if auto_save_to_db:
            processors.append(TemplatePersistenceProcessor())

        super().__init__(
            processors=processors,
            enable_persistence=enable_persistence,
            pipeline_type="CLUSTER_ANALYSIS"
        )
