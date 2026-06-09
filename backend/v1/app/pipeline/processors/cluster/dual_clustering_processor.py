from typing import List, Dict, Any
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from backend.v1.app.pipeline.base.processor import BaseProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
import logging

logger = logging.getLogger(__name__)


class DualClusteringProcessor(BaseProcessor):
    """
    双集合聚类处理器
    分别对slice和video两个集合进行独立聚类
    - slice聚类用于生成共性因子
    - video聚类用于生成创作策略
    """

    def __init__(self,
                 cluster_eps: float = 0.2,
                 cluster_min_samples: int = 3,
                 max_samples_per_cluster: int = 5):
        """
        初始化聚类处理器

        :param cluster_eps: DBSCAN聚类eps参数（余弦距离）
        :param cluster_min_samples: 聚类最小样本数
        :param max_samples_per_cluster: 每个簇最多保留的样本数
        """
        self.cluster_eps = cluster_eps
        self.cluster_min_samples = cluster_min_samples
        self.max_samples_per_cluster = max_samples_per_cluster

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        处理逻辑：
        1. 从上下文获取slice和video集合数据
        2. 分别对两个集合执行聚类
        3. 保存聚类结果到上下文
        """
        slice_data: List[Dict[str, Any]] = context.get("SLICE_COLLECTION_DATA", [])
        video_data: List[Dict[str, Any]] = context.get("VIDEO_COLLECTION_DATA", [])

        logger.info(f"开始执行双集合聚类: slice={len(slice_data)}, video={len(video_data)}")

        # 聚类slice集合
        slice_clusters = {}
        if slice_data:
            logger.info("开始聚类slice集合...")
            slice_clusters = self._perform_clustering(slice_data, "slice")
            logger.info(f"slice聚类完成，有效簇数量: {len(slice_clusters)}")

        # 聚类video集合
        video_clusters = {}
        if video_data:
            logger.info("开始聚类video集合...")
            video_clusters = self._perform_clustering(video_data, "video")
            logger.info(f"video聚类完成，有效簇数量: {len(video_clusters)}")

        # 存入上下文
        context.set("SLICE_CLUSTERS", slice_clusters)
        context.set("VIDEO_CLUSTERS", video_clusters)

        # 为了兼容现有处理器，也存入旧的key
        # 因子提取会使用slice的聚类结果
        if slice_data:
            slice_embeddings = [item["vector"] for item in slice_data]
            context.set("REPORT_EMBEDDINGS", slice_embeddings)
            context.set("HOT_REPORT_LIST", slice_data)

        logger.info(f"双聚类完成: slice簇={len(slice_clusters)}, video簇={len(video_clusters)}")

        return context

    def _perform_clustering(self, data: List[Dict[str, Any]], collection_name: str) -> Dict[int, List[Dict[str, Any]]]:
        """执行单个集合的聚类"""
        if not data:
            return {}

        # 提取向量
        vectors = [item["vector"] for item in data]
        X = np.array(vectors)

        # 计算距离矩阵并聚类
        distance_matrix = cosine_distances(X)
        clustering = DBSCAN(
            eps=self.cluster_eps,
            min_samples=self.cluster_min_samples,
            metric="precomputed"
        )
        labels = clustering.fit_predict(distance_matrix)

        # 整理聚类结果
        clusters: Dict[int, List[Dict[str, Any]]] = {}
        unique_labels = set(labels)
        unique_labels.discard(-1)  # 移除噪声点

        for label in unique_labels:
            indices = np.where(labels == label)[0].tolist()
            cluster_docs = [data[i] for i in indices]

            # 每个簇最多保留max_samples_per_cluster个样本
            if len(cluster_docs) > self.max_samples_per_cluster:
                cluster_docs = cluster_docs[:self.max_samples_per_cluster]
                logger.info(f"{collection_name}簇 {int(label)}: 样本数{len(indices)}，筛选前{self.max_samples_per_cluster}个")
            else:
                logger.info(f"{collection_name}簇 {int(label)}: 样本数{len(indices)}")

            clusters[int(label)] = cluster_docs

        return clusters
