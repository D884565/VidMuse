from typing import List, Dict, Any
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from backend.v1.app.pipeline.base.constants import REPORT_EMBEDDINGS, CLUSTER_RESULT, CLUSTER_CENTERS
import logging

logger = logging.getLogger(__name__)


class EmbeddingClusteringProcessor(BaseProcessor):
    """
    向量聚类处理器
    基于稠密向量的相似度进行无监督聚类，默认使用DBSCAN算法
    """

    def __init__(self, eps: float = 0.1, min_samples: int = 3, metric: str = "cosine"):
        """
        初始化聚类处理器

        :param eps: DBSCAN的邻域距离阈值，默认为0.1（余弦距离）
        :param min_samples: 一个簇的最小样本数
        :param metric: 距离度量方式，默认余弦距离，可选"cosine"、"euclidean"等
        """
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取向量矩阵
        2. 转换为numpy数组
        3. 使用DBSCAN进行聚类
        4. 计算每个簇的中心向量
        5. 将聚类结果存入上下文
        """
        embeddings: List[List[float]] = context.get(REPORT_EMBEDDINGS, [])

        if not embeddings:
            logger.warning("向量矩阵为空，跳过聚类")
            context.set(CLUSTER_RESULT, {})
            context.set(CLUSTER_CENTERS, {})
            return context

        logger.info(f"开始向量聚类，向量数量: {len(embeddings)}, 维度: {len(embeddings[0])}")

        # 转换为numpy数组
        X = np.array(embeddings)

        # 计算距离矩阵并执行聚类
        if self.metric == "cosine":
            distance_matrix = cosine_distances(X)
            clustering = DBSCAN(
                eps=self.eps,
                min_samples=self.min_samples,
                metric="precomputed"
            )
            labels = clustering.fit_predict(distance_matrix)
        else:
            clustering = DBSCAN(
                eps=self.eps,
                min_samples=self.min_samples,
                metric=self.metric
            )
            labels = clustering.fit_predict(X)

        # 整理聚类结果
        cluster_result: Dict[int, List[int]] = {}
        cluster_centers: Dict[int, List[float]] = {}

        # 获取所有非噪声簇
        unique_labels = set(labels)
        unique_labels.discard(-1)  # 移除噪声点

        for label in unique_labels:
            # 获取该簇的所有样本索引
            indices = np.where(labels == label)[0].tolist()
            cluster_result[label] = indices

            # 计算簇中心
            cluster_vectors = X[indices]
            center = np.mean(cluster_vectors, axis=0).tolist()
            cluster_centers[label] = center

            logger.info(f"簇 {label}: 样本数量 {len(indices)}")

        logger.info(f"聚类完成，有效簇数量: {len(cluster_result)}")

        # 存入上下文
        context.set(CLUSTER_RESULT, cluster_result)
        context.set(CLUSTER_CENTERS, cluster_centers)

        return context
