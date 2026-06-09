#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量式聚类分析工具
每处理完一个簇立即输出结果，方便实时查看
"""
import sys
import os
import json
import asyncio
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.store.collection.video_knowledge_dao import VideoKnowledgeDAO
from backend.store.collection.slice_knowledge_dao import SliceKnowledgeDAO
from backend.v1.app.pipeline.services.llm_service import LLMService
from backend.v1.app.models.inspiration_template import Factor, Strategy, InspirationTemplate
from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO, TemplateFactorRelationDAO
)
from backend.store.database.async_database import get_db

class IncrementalClusterAnalyzer:
    def __init__(self,
                 max_vectors: int = 800,
                 cluster_eps: float = 0.2,
                 cluster_min_samples: int = 3,
                 max_samples_per_cluster: int = 5):
        """
        初始化分析器
        :param max_vectors: 最大处理向量数量
        :param cluster_eps: DBSCAN聚类eps参数
        :param cluster_min_samples: DBSCAN最小样本数
        :param max_samples_per_cluster: 每个簇最多分析的样本数
        """
        self.max_vectors = max_vectors
        self.cluster_eps = cluster_eps
        self.cluster_min_samples = cluster_min_samples
        self.max_samples_per_cluster = max_samples_per_cluster

        self.video_dao = VideoKnowledgeDAO()
        self.slice_dao = SliceKnowledgeDAO()
        self.llm_service = LLMService()

        # 存储聚类结果
        self.slice_clusters: Dict[int, List[Dict[str, Any]]] = {}
        self.video_clusters: Dict[int, List[Dict[str, Any]]] = {}

        # 存储分析结果
        self.factors: Dict[str, Factor] = {}
        self.strategies: Dict[str, Strategy] = {}
        self.templates: List[InspirationTemplate] = []

        # 统计信息
        self.stats = {
            "slice_clusters": 0,
            "video_clusters": 0,
            "factors_generated": 0,
            "strategies_generated": 0,
            "templates_generated": 0,
            "failed_clusters": []
        }

        # 中间结果文件
        self.intermediate_file = f"intermediate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    def _fetch_and_cluster(self, collection_name: str) -> Dict[int, List[Dict[str, Any]]]:
        """拉取向量并执行聚类"""
        print(f"\n{'='*60}")
        print(f"📊 开始聚类 {collection_name}")
        print(f"{'='*60}")

        dao = self.slice_dao if collection_name == "slice_collection" else self.video_dao

        # 拉取数据
        print(f"1. 🔍 拉取向量和文档...")
        all_data = []
        offset = 0
        batch_size = 100

        while len(all_data) < self.max_vectors:
            try:
                from qdrant_client import models
                results, next_offset = dao._vector_client.client.scroll(
                    collection_name=dao.collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_vectors=True,
                    with_payload=True
                )

                if not results:
                    break

                for point in results:
                    if point.vector and point.payload:
                        metadata = point.payload.get("metadata", {})
                        data_item = {
                            "point_id": point.id,
                            "vector": point.vector,
                            "document": point.payload.get("document", ""),
                            "metadata": metadata,
                            "original_id": point.payload.get("original_id", "")
                        }
                        all_data.append(data_item)

                offset = next_offset
                if next_offset is None:
                    break

            except Exception as e:
                print(f"   ❌ 拉取失败: {str(e)}")
                break

        if not all_data:
            print("   ❌ 无有效数据")
            return {}

        print(f"   ✅ 成功拉取: {len(all_data)} 条数据")

        # 执行聚类
        print(f"\n2. 🧮 执行聚类...")
        vectors = [item["vector"] for item in all_data]
        X = np.array(vectors)

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
        unique_labels.discard(-1)

        for label in unique_labels:
            indices = np.where(labels == label)[0].tolist()
            cluster_docs = [all_data[i] for i in indices]
            # 每个簇最多保留max_samples_per_cluster个样本
            if len(cluster_docs) > self.max_samples_per_cluster:
                cluster_docs = cluster_docs[:self.max_samples_per_cluster]
                print(f"   簇 {label}: 样本数{len(indices)}，筛选前{self.max_samples_per_cluster}个进行分析")
            else:
                print(f"   簇 {label}: 样本数{len(indices)}")
            clusters[label] = cluster_docs

        print(f"\n   ✅ 聚类完成，有效簇数量: {len(clusters)}")
        return clusters

    def perform_clustering(self):
        """执行两个集合的聚类"""
        print("=" * 70)
        print("🚀 第一步：执行向量聚类")
        print("=" * 70)

        self.slice_clusters = self._fetch_and_cluster("slice_collection")
        self.video_clusters = self._fetch_and_cluster("video_collection")

        self.stats["slice_clusters"] = len(self.slice_clusters)
        self.stats["video_clusters"] = len(self.video_clusters)

        print(f"\n📋 聚类总览:")
        print(f"   slice簇数量: {len(self.slice_clusters)}")
        print(f"   video簇数量: {len(self.video_clusters)}")
        print(f"   总簇数量: {len(self.slice_clusters) + len(self.video_clusters)}")

        return self.slice_clusters, self.video_clusters

    def _save_intermediate_result(self, cluster_type: str, cluster_id: int, result: Dict[str, Any]):
        """保存中间结果到JSONL文件"""
        with open(self.intermediate_file, 'a', encoding='utf-8') as f:
            line = json.dumps({
                "timestamp": datetime.now().isoformat(),
                "cluster_type": cluster_type,
                "cluster_id": cluster_id,
                "result": result
            }, ensure_ascii=False)
            f.write(line + '\n')

    async def analyze_slice_clusters_incremental(self):
        """增量式分析slice聚类簇，每处理完一个就输出结果"""
        print(f"\n{'='*70}")
        print("🧠 第二步：增量分析slice聚类簇（生成共性因子）")
        print(f"{'='*70}")
        print(f"总共有 {len(self.slice_clusters)} 个slice簇需要分析")
        print(f"每个簇最多使用 {self.max_samples_per_cluster} 个样本\n")

        if not self.slice_clusters:
            print("❌ 无slice聚类结果")
            return

        factor_counter = 1

        for idx, (cluster_id, docs) in enumerate(self.slice_clusters.items(), 1):
            print(f"\n{'='*50}")
            print(f"📝 分析slice簇 {cluster_id} ({idx}/{len(self.slice_clusters)})")
            print(f"   样本数: {len(docs)}")
            print(f"{'='*50}")

            # 准备分析数据
            cluster_reports = []
            for doc in docs:
                # 截断文档，避免token过多
                content = doc["document"][:1000] + "..." if len(doc["document"]) > 1000 else doc["document"]
                cluster_reports.append({
                    "content": content,
                    "hot_score": 85,  # 默认爆款分数
                    "metadata": doc["metadata"]
                })

            try:
                print("   🤖 调用大模型提取共性因子...")
                # 调用LLM提取共性因子
                factors_data = self.llm_service.extract_common_factors(cluster_reports)

                if not factors_data:
                    print(f"   ❌ 簇 {cluster_id} 未提取到因子，跳过")
                    self.stats["failed_clusters"].append(f"slice_{cluster_id}")
                    self._save_intermediate_result("slice", cluster_id, {"status": "failed", "reason": "no_factors"})
                    continue

                # 转换为Factor模型
                cluster_factors = []
                for factor_data in factors_data:
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
                        self.factors[factor_id] = factor
                        self.stats["factors_generated"] += 1
                    except Exception as e:
                        print(f"   ❌ 构建因子失败: {str(e)}")
                        continue

                # 输出当前簇的结果
                print(f"   ✅ 成功提取 {len(cluster_factors)} 个因子:")
                for i, factor in enumerate(cluster_factors, 1):
                    print(f"     {i}. [{factor.factor_id}] {factor.name} ({factor.factor_type})")
                    print(f"        描述: {factor.description[:50]}...")

                # 保存中间结果
                self._save_intermediate_result("slice", cluster_id, {
                    "status": "success",
                    "factors": [
                        {
                            "factor_id": f.factor_id,
                            "name": f.name,
                            "factor_type": f.factor_type,
                            "description": f.description,
                            "tags": f.tags
                        } for f in cluster_factors
                    ]
                })

            except Exception as e:
                print(f"   ❌ 分析簇 {cluster_id} 失败: {str(e)}")
                self.stats["failed_clusters"].append(f"slice_{cluster_id}")
                self._save_intermediate_result("slice", cluster_id, {"status": "failed", "reason": str(e)})
                continue

        print(f"\n🎉 slice簇分析完成!")
        print(f"   成功生成因子: {len(self.factors)} 个")
        print(f"   失败簇数量: {len([c for c in self.stats['failed_clusters'] if c.startswith('slice_')])} 个")

    async def analyze_video_clusters_incremental(self):
        """增量式分析video聚类簇，每处理完一个就输出结果"""
        print(f"\n{'='*70}")
        print("🎯 第三步：增量分析video聚类簇（生成策略和模板）")
        print(f"{'='*70}")
        print(f"总共有 {len(self.video_clusters)} 个video簇需要分析")
        print(f"每个簇最多使用 {self.max_samples_per_cluster} 个样本\n")

        if not self.video_clusters:
            print("❌ 无video聚类结果")
            return

        strategy_counter = 1
        template_counter = 1
        all_factors = list(self.factors.values())

        for idx, (cluster_id, docs) in enumerate(self.video_clusters.items(), 1):
            print(f"\n{'='*50}")
            print(f"📝 分析video簇 {cluster_id} ({idx}/{len(self.video_clusters)})")
            print(f"   样本数: {len(docs)}")
            print(f"{'='*50}")

            # 准备分析数据
            cluster_reports = []
            for doc in docs:
                # 截断文档，避免token过多
                content = doc["document"][:1500] + "..." if len(doc["document"]) > 1500 else doc["document"]
                cluster_reports.append({
                    "content": content,
                    "hot_score": 85,  # 默认爆款分数
                    "metadata": doc["metadata"]
                })

            try:
                print("   🤖 第一步：调用大模型提取因子...")
                # 第一步：提取因子
                factors_data = self.llm_service.extract_common_factors(cluster_reports)
                if not factors_data:
                    print(f"   ❌ 簇 {cluster_id} 未提取到因子，跳过")
                    self.stats["failed_clusters"].append(f"video_{cluster_id}")
                    self._save_intermediate_result("video", cluster_id, {"status": "failed", "reason": "no_factors"})
                    continue

                # 转换为Factor模型（视频簇的因子也加入全局因子库）
                cluster_factors = []
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
                        self.factors[factor_id] = factor
                        self.stats["factors_generated"] += 1
                        all_factors.append(factor)
                    except Exception as e:
                        print(f"   ❌ 构建因子失败: {str(e)}")
                        continue

                print(f"   ✅ 提取到 {len(cluster_factors)} 个因子")

                # 第二步：生成策略
                print("   🤖 第二步：调用大模型生成策略...")
                if not cluster_factors:
                    print(f"   ❌ 没有可用因子，跳过策略生成")
                    self._save_intermediate_result("video", cluster_id, {"status": "failed", "reason": "no_usable_factors"})
                    continue

                strategy_data = self.llm_service.generate_strategy(cluster_reports, factors_data)
                if not strategy_data:
                    print(f"   ❌ 未生成策略，跳过")
                    self.stats["failed_clusters"].append(f"video_{cluster_id}")
                    self._save_intermediate_result("video", cluster_id, {"status": "failed", "reason": "no_strategy"})
                    continue

                # 计算成功率
                success_rate = min(0.95, 0.7 + len(docs) / 20)

                # 构建Strategy模型
                strategy_id = f"s_{strategy_counter:04d}"
                strategy_counter += 1

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
                self.strategies[strategy_id] = strategy
                self.stats["strategies_generated"] += 1

                print(f"   ✅ 生成策略: {strategy.name}")
                print(f"        ID: {strategy_id}")
                print(f"        成功率: {success_rate:.2f}")
                print(f"        核心逻辑: {strategy.core_logic[:80]}...")

                # 第三步：组装模板
                required_factors = []
                optional_factors = []

                # 匹配因子
                for factor_type in strategy.required_factor_types:
                    type_factors = [f for f in cluster_factors if f.factor_type == factor_type]
                    if type_factors:
                        required_factors.append(type_factors[0])

                for factor_type in strategy.optional_factor_types:
                    type_factors = [f for f in cluster_factors if f.factor_type == factor_type]
                    if type_factors:
                        optional_factors.append(type_factors[0])

                if not required_factors:
                    # 如果没有匹配的因子，从全局因子库中选择
                    for factor_type in strategy.required_factor_types:
                        type_factors = [f for f in all_factors if f.factor_type == factor_type]
                        if type_factors:
                            required_factors.append(type_factors[0])

                template = None
                if required_factors:
                    # 生成组合示例
                    combination_example = {
                        "strategy_id": strategy.strategy_id,
                        "strategy_name": strategy.name,
                        "core_logic": strategy.core_logic,
                        "flow": [],
                        "factors": {}
                    }

                    for i, factor in enumerate(required_factors):
                        combination_example["flow"].append({
                            "step": f"步骤{i+1}: {factor.name}",
                            "factor_id": factor.factor_id,
                            "factor_name": factor.name,
                            "example": factor.example
                        })
                        combination_example["factors"][factor.factor_id] = factor.example

                    for i, factor in enumerate(optional_factors):
                        combination_example["flow"].append({
                            "step": f"可选步骤{i+1}: {factor.name}",
                            "factor_id": factor.factor_id,
                            "factor_name": factor.name,
                            "example": factor.example
                        })
                        combination_example["factors"][factor.factor_id] = factor.example

                    template_id = f"t_{template_counter:04d}"
                    template_counter += 1

                    template = InspirationTemplate(
                        template_id=template_id,
                        strategy_id=strategy_id,
                        name=strategy.name,
                        description=strategy.description,
                        combination_example=combination_example,
                        version="v1.0",
                        success_rate=strategy.success_rate,
                        usage_count=0
                    )
                    template.strategy = strategy
                    template.required_factors = required_factors
                    template.optional_factors = optional_factors
                    self.templates.append(template)
                    self.stats["templates_generated"] += 1

                    print(f"   ✅ 组装模板: {template.name} (ID: {template_id})")
                    print(f"        必填因子: {len(required_factors)} 个, 可选因子: {len(optional_factors)} 个")

                # 保存中间结果
                self._save_intermediate_result("video", cluster_id, {
                    "status": "success",
                    "factors": [
                        {
                            "factor_id": f.factor_id,
                            "name": f.name,
                            "factor_type": f.factor_type
                        } for f in cluster_factors
                    ],
                    "strategy": {
                        "strategy_id": strategy.strategy_id,
                        "name": strategy.name,
                        "success_rate": float(strategy.success_rate),
                        "core_logic": strategy.core_logic
                    },
                    "template": {
                        "template_id": template.template_id,
                        "name": template.name
                    } if template else None
                })

            except Exception as e:
                print(f"   ❌ 分析簇 {cluster_id} 失败: {str(e)}")
                import traceback
                traceback.print_exc()
                self.stats["failed_clusters"].append(f"video_{cluster_id}")
                self._save_intermediate_result("video", cluster_id, {"status": "failed", "reason": str(e)})
                continue

        print(f"\n🎉 video簇分析完成!")
        print(f"   生成策略: {len(self.strategies)} 个")
        print(f"   生成模板: {len(self.templates)} 个")
        print(f"   失败簇数量: {len([c for c in self.stats['failed_clusters'] if c.startswith('video_')])} 个")

    async def save_to_database(self):
        """保存所有结果到数据库"""
        print(f"\n{'='*70}")
        print("💾 第四步：保存结果到数据库")
        print(f"{'='*70}")

        if not self.factors and not self.strategies and not self.templates:
            print("❌ 无数据需要保存")
            return

        db_gen = get_db()
        db = await anext(db_gen)

        try:
            # 保存因子
            saved_factors = 0
            for factor_id, factor in self.factors.items():
                existing = await FactorDAO.get_factor_by_factor_id(db, factor_id)
                if not existing:
                    factor_data = {
                        "factor_id": factor.factor_id,
                        "factor_type": factor.factor_type,
                        "name": factor.name,
                        "description": factor.description,
                        "applicable_scenarios": factor.applicable_scenarios,
                        "data_schema": factor.data_schema,
                        "example": factor.example,
                        "tags": factor.tags,
                        "popularity": factor.popularity,
                        "usage_count": factor.usage_count
                    }
                    await FactorDAO.create_factor(db, factor_data)
                    saved_factors += 1
            print(f"✅ 保存因子: {saved_factors} 个 (总生成: {len(self.factors)})")

            # 保存策略
            saved_strategies = 0
            for strategy_id, strategy in self.strategies.items():
                existing = await StrategyDAO.get_strategy_by_strategy_id(db, strategy_id)
                if not existing:
                    strategy_data = {
                        "strategy_id": strategy.strategy_id,
                        "name": strategy.name,
                        "description": strategy.description,
                        "applicable_scenarios": strategy.applicable_scenarios,
                        "core_logic": strategy.core_logic,
                        "required_factor_types": strategy.required_factor_types,
                        "optional_factor_types": strategy.optional_factor_types,
                        "combination_rules": strategy.combination_rules,
                        "success_rate": strategy.success_rate,
                        "tags": strategy.tags,
                        "usage_count": strategy.usage_count
                    }
                    await StrategyDAO.create_strategy(db, strategy_data)
                    saved_strategies += 1
            print(f"✅ 保存策略: {saved_strategies} 个 (总生成: {len(self.strategies)})")

            # 保存模板和关联关系
            saved_templates = 0
            for template in self.templates:
                existing = await InspirationTemplateDAO.get_template_by_template_id(db, template.template_id)
                if not existing:
                    template_data = {
                        "template_id": template.template_id,
                        "strategy_id": template.strategy_id,
                        "name": template.name,
                        "description": template.description,
                        "combination_example": template.combination_example,
                        "version": template.version,
                        "success_rate": template.success_rate,
                        "usage_count": template.usage_count
                    }
                    await InspirationTemplateDAO.create_template(db, template_data)

                    # 保存关联因子
                    relations = []
                    for idx, factor in enumerate(template.required_factors):
                        relations.append({
                            "template_id": template.template_id,
                            "factor_id": factor.factor_id,
                            "factor_usage_type": 1,  # 必填
                            "sort_order": idx
                        })
                    for idx, factor in enumerate(template.optional_factors):
                        relations.append({
                            "template_id": template.template_id,
                            "factor_id": factor.factor_id,
                            "factor_usage_type": 2,  # 可选
                            "sort_order": len(template.required_factors) + idx
                        })

                    if relations:
                        await TemplateFactorRelationDAO.batch_create_relations(db, relations)

                    saved_templates += 1
            print(f"✅ 保存模板: {saved_templates} 个 (总生成: {len(self.templates)})")

            await db.commit()
            print("\n🎉 所有数据保存成功!")

        except Exception as e:
            await db.rollback()
            print(f"❌ 保存失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            try:
                await anext(db_gen)
            except StopAsyncIteration:
                pass

    def generate_final_report(self, output_file: str = None):
        """生成最终分析报告"""
        if not output_file:
            output_file = f"cluster_analysis_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        print(f"\n{'='*70}")
        print(f"📄 生成最终分析报告: {output_file}")
        print(f"{'='*70}")

        # 构建报告内容
        report_content = f"""# 聚类大模型分析最终报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
## 📊 统计概览
| 指标 | 数值 |
|------|------|
| slice聚类簇数量 | {self.stats['slice_clusters']} |
| video聚类簇数量 | {self.stats['video_clusters']} |
| 总簇数量 | {self.stats['slice_clusters'] + self.stats['video_clusters']} |
| 生成因子总数 | {self.stats['factors_generated']} |
| 生成策略总数 | {self.stats['strategies_generated']} |
| 生成模板总数 | {self.stats['templates_generated']} |
| 分析失败簇数量 | {len(self.stats['failed_clusters'])} |
| 成功率 | {(self.stats['slice_clusters'] + self.stats['video_clusters'] - len(self.stats['failed_clusters'])) / (self.stats['slice_clusters'] + self.stats['video_clusters']) * 100:.1f}% |
"""

        if self.stats['failed_clusters']:
            report_content += f"\n### ❌ 分析失败的簇\n{', '.join(self.stats['failed_clusters'])}\n"

        # 因子部分
        report_content += "\n## 🧩 生成的因子列表\n"
        for factor_id, factor in self.factors.items():
            report_content += f"\n### {factor_id}: {factor.name}\n"
            report_content += f"- **类型**: {factor.factor_type}\n"
            report_content += f"- **描述**: {factor.description}\n"
            report_content += f"- **适用场景**: {', '.join(factor.applicable_scenarios)}\n"
            report_content += f"- **标签**: {', '.join(factor.tags)}\n"
            report_content += f"- **流行度**: {factor.popularity:.2f}\n"

        # 策略部分
        report_content += "\n## 🎯 生成的策略列表\n"
        for strategy_id, strategy in self.strategies.items():
            report_content += f"\n### {strategy_id}: {strategy.name}\n"
            report_content += f"- **描述**: {strategy.description}\n"
            report_content += f"- **核心逻辑**: {strategy.core_logic}\n"
            report_content += f"- **成功率**: {strategy.success_rate:.2f}\n"
            report_content += f"- **必填因子类型**: {', '.join(strategy.required_factor_types)}\n"
            report_content += f"- **可选因子类型**: {', '.join(strategy.optional_factor_types)}\n"
            report_content += f"- **组合规则**: {strategy.combination_rules}\n"
            report_content += f"- **标签**: {', '.join(strategy.tags)}\n"

        # 模板部分
        report_content += "\n## 📝 生成的模板列表\n"
        for template in self.templates:
            report_content += f"\n### {template.template_id}: {template.name}\n"
            report_content += f"- **关联策略**: {template.strategy.name} (ID: {template.strategy_id})\n"
            report_content += f"- **成功率**: {template.success_rate:.2f}\n"
            report_content += f"- **必填因子**: {len(template.required_factors)} 个\n"
            report_content += f"- **可选因子**: {len(template.optional_factors)} 个\n"
            report_content += f"- **组合示例流程:**\n"
            for step in template.combination_example["flow"]:
                report_content += f"  1. {step['step']}\n"

        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"✅ 最终报告生成完成: {output_file}")
        return output_file

async def main():
    print("=" * 70)
    print("🚀 增量式聚类大模型分析工具")
    print("每处理完一个簇立即输出结果")
    print("=" * 70)

    analyzer = IncrementalClusterAnalyzer(
        max_vectors=800,
        cluster_eps=0.2,
        cluster_min_samples=3,
        max_samples_per_cluster=5  # 每个簇最多选5个样本分析
    )

    # 1. 执行聚类
    analyzer.perform_clustering()

    # 2. 增量分析slice簇
    await analyzer.analyze_slice_clusters_incremental()

    # 3. 增量分析video簇
    await analyzer.analyze_video_clusters_incremental()

    # 4. 保存到数据库
    await analyzer.save_to_database()

    # 5. 生成最终报告
    report_file = analyzer.generate_final_report()

    print("\n" + "=" * 70)
    print("🎉 任务全部完成!")
    print(f"📊 生成因子: {len(analyzer.factors)} 个")
    print(f"🎯 生成策略: {len(analyzer.strategies)} 个")
    print(f"📝 生成模板: {len(analyzer.templates)} 个")
    print(f"📄 分析报告: {report_file}")
    print(f"💾 中间结果: {analyzer.intermediate_file}")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    asyncio.run(main())
