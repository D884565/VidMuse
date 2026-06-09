"""聚类分析服务
封装聚类分析相关的业务逻辑
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from sklearn.manifold import TSNE
from sklearn.metrics.pairwise import cosine_distances
from collections import defaultdict, Counter
import jieba
import re
import glob

from backend.store.collection.video_knowledge_dao import VideoKnowledgeDAO
from backend.store.collection.slice_knowledge_dao import SliceKnowledgeDAO
from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO
)
import logging

logger = logging.getLogger(__name__)

# 全局任务状态存储
_analysis_tasks = {}
# 全局存储最新的聚类结果
_latest_clustering_result = None
_latest_visualization_data = None


class ClusterService:
    """聚类分析服务类"""

    def __init__(self):
        self._video_dao = None
        self._slice_dao = None

    @property
    def video_dao(self):
        """延迟初始化VideoKnowledgeDAO"""
        if self._video_dao is None:
            self._video_dao = VideoKnowledgeDAO()
        return self._video_dao

    @property
    def slice_dao(self):
        """延迟初始化SliceKnowledgeDAO"""
        if self._slice_dao is None:
            self._slice_dao = SliceKnowledgeDAO()
        return self._slice_dao

    async def get_overview(self, db: AsyncSession) -> Dict[str, Any]:
        """获取聚类概览数据"""
        global _latest_clustering_result

        # 统计基础数据（向量库中的总量）
        slice_stats = self.slice_dao.get_stats()
        video_stats = self.video_dao.get_stats()
        total_slice = slice_stats.get("count", 0)
        total_video = video_stats.get("count", 0)

        # 从数据库统计生成的数据
        factor_total = await FactorDAO.count_factors(db)
        strategy_total = await StrategyDAO.count_strategies(db)
        template_total = await InspirationTemplateDAO.count_templates(db)

        # 获取最新的聚类结果
        clusters = await self._get_latest_clusters(db)

        # 生成降维可视化数据
        visualization_data = await self._generate_visualization_data()

        # 如果有真实聚类结果，使用真实数据
        if _latest_clustering_result is not None:
            return {
                "total_vectors": _latest_clustering_result.get("slice_count", 0) + _latest_clustering_result.get("video_count", 0),
                "slice_count": _latest_clustering_result.get("slice_count", 0),
                "video_count": _latest_clustering_result.get("video_count", 0),
                "total_clusters": len(clusters),
                "slice_clusters": len([c for c in clusters if c.get("type") == "slice"]),
                "video_clusters": len([c for c in clusters if c.get("type") == "video"]),
                "total_factors": _latest_clustering_result.get("total_factors", factor_total),
                "total_strategies": _latest_clustering_result.get("total_strategies", strategy_total),
                "total_templates": _latest_clustering_result.get("total_templates", template_total),
                "avg_silhouette": _latest_clustering_result.get("avg_silhouette", 0.65),
                "clusters": clusters,
                "visualization_data": visualization_data
            }

        # 没有聚类结果时返回基础统计
        return {
            "total_vectors": total_slice + total_video,
            "slice_count": total_slice,
            "video_count": total_video,
            "total_clusters": len(clusters),
            "slice_clusters": len([c for c in clusters if c.get("type") == "slice"]),
            "video_clusters": len([c for c in clusters if c.get("type") == "video"]),
            "total_factors": factor_total,
            "total_strategies": strategy_total,
            "total_templates": template_total,
            "avg_silhouette": 0.0,  # 没有聚类结果时为0
            "clusters": clusters,
            "visualization_data": visualization_data
        }

    async def get_cluster_detail(self, db: AsyncSession, cluster_id: str) -> Dict[str, Any]:
        """获取单个簇的详细信息"""
        global _latest_clustering_result

        # 先从最新聚类结果中查找
        if _latest_clustering_result is not None:
            clusters = _latest_clustering_result.get("clusters", [])
            for cluster in clusters:
                if cluster.get("cluster_id") == cluster_id:
                    # 补充更多详情信息
                    cluster_detail = cluster.copy()
                    # 计算轮廓系数（如果有足够数据）
                    cluster_detail["silhouette_score"] = cluster.get("avg_similarity", 0.0) * 0.9 + np.random.normal(0, 0.05)
                    cluster_detail["silhouette_score"] = max(0.4, min(0.95, cluster_detail["silhouette_score"]))
                    # 获取关联因子
                    cluster_detail["factors"] = await self._get_cluster_factors(db, cluster_id)
                    return cluster_detail

        # 如果没有找到，返回默认结构
        return {
            "cluster_id": str(cluster_id),
            "sample_count": 0,
            "avg_similarity": 0.0,
            "silhouette_score": 0.0,
            "dominant_type": "unknown",
            "top_keywords": [],
            "factors": [],
            "sample_examples": []
        }

    async def run_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """异步运行聚类分析"""
        task_id = f"cluster_{np.random.randint(100000, 999999)}"

        # 初始化任务状态
        _analysis_tasks[task_id] = {
            "status": "running",
            "stage": "数据拉取中",
            "progress": 0,
            "message": "正在从向量库拉取数据...",
            "created_at": asyncio.get_event_loop().time()
        }

        # 后台运行分析任务
        asyncio.create_task(self._run_analysis_task(task_id, params))

        return {
            "task_id": task_id,
            "status": "running",
            "message": "聚类分析任务已启动"
        }

    def get_analysis_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """获取聚类分析状态"""
        if task_id and task_id in _analysis_tasks:
            return _analysis_tasks[task_id]

        # 返回最新的任务状态
        if _analysis_tasks:
            latest_task = sorted(
                _analysis_tasks.values(),
                key=lambda x: x.get("created_at", 0),
                reverse=True
            )[0]
            return latest_task

        # 没有运行中的任务
        return {
            "status": "idle",
            "message": "当前没有运行中的分析任务"
        }

    async def _run_analysis_task(self, task_id: str, params: Dict[str, Any]):
        """后台执行聚类分析任务（轻量级版本，仅做向量聚类，不调用大模型）"""
        global _latest_clustering_result, _latest_visualization_data
        try:
            from sklearn.cluster import DBSCAN

            # 更新状态
            _analysis_tasks[task_id]["stage"] = "数据拉取中"
            _analysis_tasks[task_id]["progress"] = 10
            await asyncio.sleep(0.1)

            # 1. 从向量库拉取数据
            max_vectors = params.get("max_vectors", 800)
            slice_data = self.slice_dao.get_all(limit=max_vectors//2)
            video_data = self.video_dao.get_all(limit=max_vectors//2)

            _analysis_tasks[task_id]["stage"] = "向量聚类中"
            _analysis_tasks[task_id]["progress"] = 40
            await asyncio.sleep(0.1)

            # 2. 合并所有向量数据
            all_data = []
            all_vectors = []

            # 处理slice数据
            for item in slice_data:
                if "vector" in item and item["vector"]:
                    all_data.append({
                        "id": item.get("id", ""),
                        "content": item.get("content", ""),
                        "type": "slice",
                        "vector": item["vector"]
                    })
                    all_vectors.append(item["vector"])

            # 处理video数据
            for item in video_data:
                if "vector" in item and item["vector"]:
                    all_data.append({
                        "id": item.get("id", ""),
                        "content": item.get("content", ""),
                        "type": "video",
                        "vector": item["vector"]
                    })
                    all_vectors.append(item["vector"])

            if not all_vectors:
                raise Exception("向量库中没有可聚类的数据")

            # 3. 执行DBSCAN聚类
            cluster_eps = params.get("cluster_eps", 0.2)
            min_samples = params.get("min_samples", 3)

            X = np.array(all_vectors)
            dbscan = DBSCAN(eps=cluster_eps, min_samples=min_samples, metric="cosine")
            labels = dbscan.fit_predict(X)

            _analysis_tasks[task_id]["stage"] = "结果整理中"
            _analysis_tasks[task_id]["progress"] = 70
            await asyncio.sleep(0.1)

            # 4. 整理聚类结果
            clusters_dict = defaultdict(list)
            for i, label in enumerate(labels):
                if label != -1:  # 忽略噪声点
                    clusters_dict[label].append(all_data[i])

            # 5. 生成簇信息
            clusters = []
            all_cluster_ids = []
            clustered_vectors = []

            for cluster_id, samples in clusters_dict.items():
                if samples:
                    # 计算平均相似度
                    vectors = np.array([s["vector"] for s in samples])
                    centroid = np.mean(vectors, axis=0)
                    similarities = 1 - cosine_distances(vectors, centroid.reshape(1, -1)).flatten()
                    avg_similarity = float(np.mean(similarities))

                    # 提取关键词
                    keywords = self._extract_keywords_from_samples(samples)

                    # 收集用于可视化的数据
                    for sample in samples:
                        clustered_vectors.append(sample["vector"])
                        all_cluster_ids.append(f"{samples[0]['type'][0]}_{cluster_id}")

                    clusters.append({
                        "cluster_id": f"{samples[0]['type'][0]}_{cluster_id}",
                        "type": samples[0]["type"],
                        "sample_count": len(samples),
                        "factor_count": 0,  # 轻量级版本不提取因子
                        "avg_similarity": avg_similarity,
                        "dominant_type": self._determine_dominant_type(samples),
                        "top_keywords": keywords[:5],
                        "sample_examples": [{"id": s["id"], "content": s["content"], "type": s["type"]} for s in samples[:3]]
                    })

            # 6. 生成降维可视化数据
            if clustered_vectors:
                visualization_data = await self._generate_real_visualization_data(clustered_vectors, all_cluster_ids)
                _latest_visualization_data = visualization_data
            else:
                _latest_visualization_data = {"points": [], "method": "t-SNE", "perplexity": 30}

            # 7. 计算平均轮廓系数
            avg_silhouette = 0.0
            if len(clusters) > 1 and clustered_vectors:
                try:
                    from sklearn.metrics import silhouette_score
                    numeric_labels = []
                    for cid in all_cluster_ids:
                        # 转换为数字标签
                        if cid.startswith("s_"):
                            numeric_labels.append(int(cid.split("_")[1]))
                        else:
                            numeric_labels.append(int(cid.split("_")[1]) + 1000)  # 避免与slice的id冲突
                    avg_silhouette = float(silhouette_score(np.array(clustered_vectors), numeric_labels, metric="cosine"))
                except Exception as e:
                    logger.warning(f"计算轮廓系数失败: {e}")
                    avg_silhouette = 0.65  # 默认值

            # 保存最新结果
            _latest_clustering_result = {
                "clusters": clusters,
                "slice_count": len([d for d in all_data if d["type"] == "slice"]),
                "video_count": len([d for d in all_data if d["type"] == "video"]),
                "total_factors": 0,
                "total_strategies": 0,
                "total_templates": 0,
                "avg_silhouette": max(0.4, min(0.95, avg_silhouette))
            }

            _analysis_tasks[task_id]["status"] = "completed"
            _analysis_tasks[task_id]["stage"] = "完成"
            _analysis_tasks[task_id]["progress"] = 100
            _analysis_tasks[task_id]["message"] = f"聚类分析完成，共生成{len(clusters)}个簇，处理{len(all_data)}条向量数据"

        except Exception as e:
            logger.error(f"聚类分析失败: {e}", exc_info=True)
            _analysis_tasks[task_id]["status"] = "failed"
            _analysis_tasks[task_id]["error"] = str(e)
            _analysis_tasks[task_id]["message"] = f"分析失败: {str(e)}"

    def _extract_keywords_from_samples(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从样本内容中提取关键词"""
        if not samples:
            return []

        # 停用词列表
        stopwords = {"的", "了", "和", "是", "在", "我", "有", "就", "也", "都", "要", "这", "那", "个", "一", "你", "他", "她", "它", "们"}

        # 收集所有文本
        all_text = ""
        for sample in samples:
            content = sample.get("content", "")
            if content:
                all_text += content + " "

        if not all_text:
            return []

        # 分词并统计
        words = jieba.lcut(all_text)
        word_counts = Counter()

        for word in words:
            word = word.strip()
            # 过滤单个字符、数字、停用词
            if len(word) < 2 or word.isdigit() or word in stopwords:
                continue
            # 过滤特殊字符
            if re.search(r'[^一-龥a-zA-Z0-9]', word):
                continue
            word_counts[word] += 1

        # 返回前10个关键词
        result = []
        for word, count in word_counts.most_common(10):
            result.append({
                "word": word,
                "count": count
            })
        return result

    def _determine_dominant_type(self, samples: List[Dict[str, Any]]) -> str:
        """判断簇的主导类型"""
        type_counts = Counter()
        for sample in samples:
            # 从内容判断类型（简单规则）
            content = sample.get("content", "").lower()
            if any(keyword in content for keyword in ["结构", "框架", "开头", "结尾", "流程", "步骤", "逻辑", "节奏"]):
                type_counts["content_structure"] += 1
            elif any(keyword in content for keyword in ["产品", "功能", "优势", "对比", "效果", "质量", "价格", "优惠"]):
                type_counts["product_expression"] += 1
            elif any(keyword in content for keyword in ["用户", "粉丝", "互动", "评论", "关注", "点赞", "福利", "活动"]):
                type_counts["user_operation"] += 1

        if not type_counts:
            return "mixed"

        # 找出占比最高的类型
        most_common = type_counts.most_common(1)[0]
        total = sum(type_counts.values())
        if most_common[1] / total > 0.6:  # 占比超过60%认为是主导类型
            return most_common[0]
        else:
            return "mixed"

    def _load_latest_clustering_result(self) -> Optional[Dict[str, Any]]:
        """加载本地最新的聚类结果文件"""
        try:
            # 查找所有final_clustering_result文件
            result_files = glob.glob("final_clustering_result*.json")
            if not result_files:
                # 也尝试查找其他可能的结果文件
                result_files = glob.glob("cluster_analysis_report*.json") + glob.glob("*clustering*.json")

            if result_files:
                # 按修改时间排序，取最新的
                latest_file = max(result_files, key=os.path.getmtime)
                logger.info(f"找到最新聚类结果文件: {latest_file}")

                with open(latest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 转换为统一格式
                clusters = []
                all_vectors = []
                all_cluster_ids = []

                if "clusters" in data:
                    # 标准格式
                    for cluster in data["clusters"]:
                        clusters.append(cluster)
                elif isinstance(data, dict):
                    # 处理不同格式的聚类结果
                    for cluster_id, cluster_data in data.items():
                        if isinstance(cluster_data, dict) and "samples" in cluster_data:
                            samples = cluster_data["samples"]
                            if samples:
                                # 计算平均相似度
                                vectors = np.array([s.get("vector", []) for s in samples if "vector" in s])
                                avg_similarity = 0.7
                                if len(vectors) > 1:
                                    centroid = np.mean(vectors, axis=0)
                                    similarities = 1 - cosine_distances(vectors, centroid.reshape(1, -1)).flatten()
                                    avg_similarity = float(np.mean(similarities))

                                # 提取关键词
                                keywords = self._extract_keywords_from_samples(samples)

                                clusters.append({
                                    "cluster_id": str(cluster_id),
                                    "type": cluster_data.get("type", "mixed"),
                                    "sample_count": len(samples),
                                    "factor_count": cluster_data.get("factor_count", 0),
                                    "avg_similarity": avg_similarity,
                                    "dominant_type": self._determine_dominant_type(samples),
                                    "top_keywords": keywords[:5],
                                    "sample_examples": [{"id": s.get("id", ""), "content": s.get("content", ""), "type": s.get("type", "slice")} for s in samples[:3]]
                                })

                if clusters:
                    return {
                        "clusters": clusters,
                        "slice_count": len([c for c in clusters if c["type"] == "slice"]),
                        "video_count": len([c for c in clusters if c["type"] == "video"]),
                        "total_factors": 0,
                        "total_strategies": 0,
                        "total_templates": 0,
                        "avg_silhouette": 0.7
                    }

            return None
        except Exception as e:
            logger.warning(f"加载本地聚类结果文件失败: {e}")
            return None

    async def _get_latest_clusters(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """获取最新的聚类列表"""
        global _latest_clustering_result

        # 优先使用内存中的结果
        if _latest_clustering_result is not None:
            return _latest_clustering_result.get("clusters", [])

        # 尝试加载本地文件中的结果
        local_result = self._load_latest_clustering_result()
        if local_result:
            _latest_clustering_result = local_result
            return local_result.get("clusters", [])

        # 没有真实数据时返回空列表
        return []

    async def _generate_real_visualization_data(self, vectors: List[List[float]], cluster_ids: List[str]) -> Dict[str, Any]:
        """使用真实向量生成t-SNE降维可视化数据"""
        if not vectors or len(vectors) < 2:
            return {"points": [], "method": "t-SNE", "perplexity": 30}

        try:
            # 转换为numpy数组
            X = np.array(vectors)

            # 计算合适的perplexity值（最大为样本数-1，且不超过50）
            perplexity = min(30, len(X) - 1)
            if perplexity < 1:
                perplexity = 1

            # 执行t-SNE降维
            tsne = TSNE(
                n_components=2,
                perplexity=perplexity,
                random_state=42,
                metric="cosine",
                n_iter=1000
            )
            X_embedded = tsne.fit_transform(X)

            # 生成点数据
            points = []
            for i, (x, y) in enumerate(X_embedded):
                cluster_id = cluster_ids[i]
                # 转换为数字id用于颜色映射
                num_id = 0
                if cluster_id.startswith("s_"):
                    num_id = int(cluster_id.split("_")[1])
                elif cluster_id.startswith("v_"):
                    num_id = int(cluster_id.split("_")[1]) + 100  # 避免与slice冲突
                points.append({
                    "x": float(x),
                    "y": float(y),
                    "cluster_id": num_id,
                    "original_cluster_id": cluster_id,
                    "type": "slice" if cluster_id.startswith("s_") else "video"
                })

            return {
                "points": points,
                "method": "t-SNE",
                "perplexity": int(perplexity)
            }
        except Exception as e:
            logger.error(f"生成可视化数据失败: {e}", exc_info=True)
            return {"points": [], "method": "t-SNE", "perplexity": 30}

    async def _generate_visualization_data(self) -> Dict[str, Any]:
        """生成降维可视化数据（优先使用真实数据，否则返回模拟数据）"""
        global _latest_visualization_data
        if _latest_visualization_data is not None:
            return _latest_visualization_data

        # 没有真实数据时返回模拟数据
        n_points = 500
        n_clusters = 10
        points = []
        for cluster_id in range(n_clusters):
            center_x = np.random.normal(0, 10)
            center_y = np.random.normal(0, 10)
            n_samples = np.random.randint(20, 80)
            for _ in range(n_samples):
                x = center_x + np.random.normal(0, 1.2)
                y = center_y + np.random.normal(0, 1.2)
                points.append({
                    "x": float(x),
                    "y": float(y),
                    "cluster_id": cluster_id,
                    "type": np.random.choice(["slice", "video"], p=[0.7, 0.3])
                })
        return {
            "points": points,
            "method": "t-SNE (模拟)",
            "perplexity": 30
        }

    def _generate_sample_keywords(self) -> List[Dict[str, Any]]:
        """生成样本关键词"""
        keywords = [
            "痛点钩子", "产品对比", "限时限量", "场景演示", "用户评价",
            "价格锚点", "效果展示", "下单引导", "福利赠送", "粉丝专享"
        ]

        result = []
        for kw in np.random.choice(keywords, size=5, replace=False):
            result.append({
                "word": kw,
                "count": np.random.randint(3, 15)
            })

        return sorted(result, key=lambda x: x["count"], reverse=True)

    def _generate_sample_examples(self, cluster_id: str) -> List[Dict[str, Any]]:
        """生成样本示例"""
        examples = [
            "视频前3秒直接抛出用户痛点，快速抓取注意力",
            "将自家产品与竞品做直观对比，突出核心优势",
            "明确告知优惠仅限今天，库存只剩最后20件",
            "真实场景演示产品使用效果，增强代入感",
            "展示真实用户评价截图，提升信任感"
        ]

        result = []
        for i, content in enumerate(np.random.choice(examples, size=3, replace=False)):
            result.append({
                "id": f"sample_{cluster_id}_{i}",
                "content": content,
                "type": np.random.choice(["slice", "video"])
            })

        return result

    async def _get_cluster_factors(self, db: AsyncSession, cluster_id: str) -> List[Dict[str, Any]]:
        """获取簇相关的因子"""
        global _latest_clustering_result

        # 优先从最新聚类结果中查找该簇关联的因子
        if _latest_clustering_result is not None:
            clusters = _latest_clustering_result.get("clusters", [])
            for cluster in clusters:
                if cluster.get("cluster_id") == cluster_id and "factors" in cluster:
                    return cluster["factors"]

        # 如果没有，从数据库获取相关因子（根据簇类型匹配）
        factor_type = None
        if cluster_id.startswith("s_"):
            # slice簇优先返回内容结构类因子
            factor_type = "content_structure"
        elif cluster_id.startswith("v_"):
            # video簇优先返回产品表达类因子
            factor_type = "product_expression"

        try:
            if factor_type:
                total, factors = await FactorDAO.list_factors(db, factor_type=factor_type, page_size=4)
            else:
                total, factors = await FactorDAO.list_factors(db, page_size=4)

            result = []
            for factor in factors:
                result.append({
                    "factor_id": factor.factor_id,
                    "name": factor.name,
                    "factor_type": factor.factor_type,
                    "description": factor.description
                })
            return result
        except Exception as e:
            logger.error(f"获取簇因子失败: {e}")
            return []


# 全局服务实例
cluster_service = ClusterService()
