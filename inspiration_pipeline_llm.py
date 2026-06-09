#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于大模型的灵感模板生成流水线
完整流程：向量拉取 → 聚类分析 → LLM分析 → 落库 → 生成报告
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

class InspirationPipelineLLM:
    def __init__(self,
                 use_slice_collection: bool = True,
                 max_vectors: int = 500,
                 cluster_eps: float = 0.2,
                 cluster_min_samples: int = 3):
        """
        初始化流水线
        :param use_slice_collection: 是否使用slice_collection，False使用video_collection
        :param max_vectors: 最大处理向量数量
        :param cluster_eps: DBSCAN聚类eps参数
        :param cluster_min_samples: DBSCAN最小样本数
        """
        self.use_slice_collection = use_slice_collection
        self.max_vectors = max_vectors
        self.cluster_eps = cluster_eps
        self.cluster_min_samples = cluster_min_samples

        # 初始化DAO
        self.video_dao = VideoKnowledgeDAO()
        self.slice_dao = SliceKnowledgeDAO()
        self.llm_service = LLMService()

        # 结果存储
        self.vectors_data: List[Dict[str, Any]] = []  # 所有向量数据（包含向量、payload、文档）
        self.cluster_result: Dict[int, List[int]] = {}  # 聚类结果 {簇ID: [索引列表]}
        self.cluster_centers: Dict[int, List[float]] = {}  # 簇中心
        self.cluster_analyses: Dict[int, Dict[str, Any]] = {}  # 每个簇的LLM分析结果
        self.factors: Dict[str, Factor] = {}  # 所有因子
        self.strategies: Dict[str, Strategy] = {}  # 所有策略
        self.templates: List[InspirationTemplate] = []  # 所有模板

        # 统计信息
        self.stats = {
            "total_vectors": 0,
            "valid_clusters": 0,
            "noise_points": 0,
            "factors_generated": 0,
            "strategies_generated": 0,
            "templates_generated": 0
        }

    def _get_collection_dao(self):
        """获取当前使用的集合DAO"""
        return self.slice_dao if self.use_slice_collection else self.video_dao

    def _get_collection_name(self):
        """获取当前使用的集合名称"""
        return "slice_collection" if self.use_slice_collection else "video_collection"

    def fetch_vectors_and_documents(self) -> List[Dict[str, Any]]:
        """从向量库批量拉取向量和对应的文档内容"""
        print(f"\n{'='*70}")
        print(f"1. 从{self._get_collection_name()}拉取向量和文档")
        print(f"{'='*70}")

        dao = self._get_collection_dao()
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

                print(f"已拉取: {len(all_data)} 条")

            except Exception as e:
                print(f"拉取数据失败: {str(e)}")
                break

        self.vectors_data = all_data[:self.max_vectors]
        self.stats["total_vectors"] = len(self.vectors_data)
        print(f"\n成功拉取有效数据: {len(self.vectors_data)} 条")
        return self.vectors_data

    def perform_clustering(self) -> Dict[int, List[int]]:
        """执行向量聚类"""
        print(f"\n{'='*70}")
        print("2. 执行向量聚类分析")
        print(f"{'='*70}")

        if not self.vectors_data:
            print("没有向量数据，跳过聚类")
            return {}

        # 提取向量矩阵
        vectors = [item["vector"] for item in self.vectors_data]
        X = np.array(vectors)
        print(f"向量矩阵维度: {X.shape}")
        print(f"聚类参数: eps={self.cluster_eps}, min_samples={self.cluster_min_samples}, 距离度量=余弦距离")

        # 计算余弦距离矩阵
        distance_matrix = cosine_distances(X)

        # DBSCAN聚类
        clustering = DBSCAN(
            eps=self.cluster_eps,
            min_samples=self.cluster_min_samples,
            metric="precomputed"
        )
        labels = clustering.fit_predict(distance_matrix)

        # 整理聚类结果
        cluster_result: Dict[int, List[int]] = {}
        cluster_centers: Dict[int, List[float]] = {}

        # 获取所有非噪声簇
        unique_labels = set(labels)
        unique_labels.discard(-1)  # 移除噪声点

        for label in unique_labels:
            indices = np.where(labels == label)[0].tolist()
            cluster_result[label] = indices

            # 计算簇中心
            cluster_vectors = X[indices]
            center = np.mean(cluster_vectors, axis=0).tolist()
            cluster_centers[label] = center

            print(f"簇 {label}: {len(indices)} 个样本")

        self.cluster_result = cluster_result
        self.cluster_centers = cluster_centers
        self.stats["valid_clusters"] = len(cluster_result)
        self.stats["noise_points"] = list(labels).count(-1)

        print(f"\n聚类完成:")
        print(f"  有效簇数量: {len(cluster_result)}")
        print(f"  噪声点数量: {self.stats['noise_points']}")
        print(f"  聚类覆盖率: {(len(vectors) - self.stats['noise_points']) / len(vectors) * 100:.1f}%")

        return cluster_result

    async def analyze_clusters_with_llm(self) -> Dict[int, Dict[str, Any]]:
        """使用大模型分析每个聚类簇的内容"""
        print(f"\n{'='*70}")
        print("3. 大模型聚类分析")
        print(f"{'='*70}")

        if not self.cluster_result:
            print("没有聚类结果，跳过分析")
            return {}

        cluster_analyses = {}

        for cluster_id, indices in self.cluster_result.items():
            print(f"\n分析簇 {cluster_id} (样本数: {len(indices)})...")

            # 获取该簇的所有文档内容（最多取10个，避免token过多）
            cluster_docs = []
            for idx in indices[:10]:
                doc = self.vectors_data[idx]["document"]
                # 截断过长的文档
                if len(doc) > 1000:
                    doc = doc[:1000] + "...[内容截断]"
                cluster_docs.append(doc)

            if not cluster_docs:
                print(f"簇 {cluster_id} 没有有效文档，跳过")
                continue

            try:
                # 第一步：提取共性特征
                print(f"  提取共性特征...")
                factors_data = self.llm_service.extract_common_factors([
                    {"content": doc, "hot_score": 85} for doc in cluster_docs
                ])

                if not factors_data:
                    print(f"  未提取到因子，跳过")
                    continue

                # 第二步：生成策略（如果是video集合）
                strategy_data = None
                if not self.use_slice_collection:
                    print(f"  生成创作策略...")
                    strategy_data = self.llm_service.generate_strategy(
                        [{"content": doc, "hot_score": 85} for doc in cluster_docs],
                        factors_data
                    )

                # 保存分析结果
                cluster_analyses[cluster_id] = {
                    "cluster_id": cluster_id,
                    "sample_count": len(indices),
                    "sample_documents": cluster_docs,
                    "factors": factors_data,
                    "strategy": strategy_data
                }

                print(f"  分析完成: 提取到{len(factors_data)}个因子" +
                      (f", 1个策略" if strategy_data else ""))

            except Exception as e:
                print(f"  分析簇 {cluster_id} 失败: {str(e)}")
                continue

        self.cluster_analyses = cluster_analyses
        print(f"\n簇分析完成，成功分析 {len(cluster_analyses)} 个簇")
        return cluster_analyses

    def build_models_from_analysis(self):
        """从LLM分析结果构建Factor、Strategy、Template模型"""
        print(f"\n{'='*70}")
        print("4. 构建数据模型")
        print(f"{'='*70}")

        if not self.cluster_analyses:
            print("没有分析结果，跳过模型构建")
            return

        factor_counter = 1
        strategy_counter = 1
        template_counter = 1

        for cluster_id, analysis in self.cluster_analyses.items():
            # 构建Factor模型
            factors_data = analysis.get("factors", [])
            cluster_factors = []

            for factor_data in factors_data:
                factor_id = f"f_{factor_counter:04d}"
                factor_counter += 1

                try:
                    factor = Factor(
                        factor_id=factor_id,
                        factor_type=factor_data.get("factor_type", "content_structure"),
                        name=factor_data.get("name", f"因子_{factor_id}"),
                        description=factor_data.get("description", ""),
                        applicable_scenarios=factor_data.get("applicable_scenarios", ["通用"]),
                        data_schema=factor_data.get("data_schema", {}),
                        example=factor_data.get("example", {}),
                        tags=factor_data.get("tags", []) + [f"cluster_{cluster_id}"],
                        popularity=factor_data.get("popularity", 0.8),
                        usage_count=0
                    )
                    cluster_factors.append(factor)
                    self.factors[factor_id] = factor
                except Exception as e:
                    print(f"构建因子失败: {str(e)}")
                    continue

            # 如果是video集合，构建Strategy和Template
            strategy = None
            if not self.use_slice_collection:
                strategy_data = analysis.get("strategy")
                if strategy_data and cluster_factors:
                    strategy_id = f"s_{strategy_counter:04d}"
                    strategy_counter += 1

                    try:
                        # 计算成功率
                        success_rate = min(0.95, 0.7 + len(analysis['sample_count']) / 50)

                        strategy = Strategy(
                            strategy_id=strategy_id,
                            name=strategy_data.get("name", f"策略_{strategy_id}"),
                            description=strategy_data.get("description", ""),
                            applicable_scenarios=strategy_data.get("applicable_scenarios", ["通用"]),
                            core_logic=strategy_data.get("core_logic", ""),
                            required_factor_types=strategy_data.get("required_factor_types", ["content_structure"]),
                            optional_factor_types=strategy_data.get("optional_factor_types", []),
                            combination_rules=strategy_data.get("combination_rules", ""),
                            success_rate=success_rate,
                            tags=strategy_data.get("tags", []) + [f"cluster_{cluster_id}"],
                            usage_count=0
                        )
                        self.strategies[strategy_id] = strategy

                        # 组装模板
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

                        if required_factors:
                            template_id = f"t_{template_counter:04d}"
                            template_counter += 1

                            # 生成组合示例
                            combination_example = self._generate_combination_example(
                                strategy, required_factors, optional_factors
                            )

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

                    except Exception as e:
                        print(f"构建策略/模板失败: {str(e)}")
                        continue

        self.stats["factors_generated"] = len(self.factors)
        self.stats["strategies_generated"] = len(self.strategies)
        self.stats["templates_generated"] = len(self.templates)

        print(f"\n模型构建完成:")
        print(f"  生成因子: {len(self.factors)} 个")
        print(f"  生成策略: {len(self.strategies)} 个")
        print(f"  生成模板: {len(self.templates)} 个")

    def _generate_combination_example(self, strategy: Strategy, required_factors: List[Factor], optional_factors: List[Factor]) -> Dict[str, Any]:
        """生成模板组合示例"""
        flow = []
        for i, factor in enumerate(required_factors):
            flow.append({
                "step": f"步骤{i+1}: {factor.name}",
                "factor_id": factor.factor_id,
                "factor_name": factor.name,
                "example": factor.example
            })

        for i, factor in enumerate(optional_factors):
            flow.append({
                "step": f"可选步骤{i+1}: {factor.name}",
                "factor_id": factor.factor_id,
                "factor_name": factor.name,
                "example": factor.example
            })

        factors_map = {}
        for factor in required_factors + optional_factors:
            factors_map[factor.factor_id] = factor.example

        return {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.name,
            "core_logic": strategy.core_logic,
            "flow": flow,
            "factors": factors_map
        }

    async def save_to_database(self):
        """保存所有数据到数据库"""
        print(f"\n{'='*70}")
        print("5. 保存到数据库")
        print(f"{'='*70}")

        if not self.factors and not self.strategies and not self.templates:
            print("没有数据需要保存")
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
            print(f"保存因子: {saved_factors} 个")

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
            print(f"保存策略: {saved_strategies} 个")

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
                            "factor_usage_type": 1,
                            "sort_order": idx
                        })
                    for idx, factor in enumerate(template.optional_factors):
                        relations.append({
                            "template_id": template.template_id,
                            "factor_id": factor.factor_id,
                            "factor_usage_type": 2,
                            "sort_order": len(template.required_factors) + idx
                        })

                    if relations:
                        await TemplateFactorRelationDAO.batch_create_relations(db, relations)

                    saved_templates += 1
            print(f"保存模板: {saved_templates} 个")

            await db.commit()
            print("\n✅ 所有数据保存成功!")

        except Exception as e:
            await db.rollback()
            print(f"保存失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            try:
                await anext(db_gen)
            except StopAsyncIteration:
                pass

    def generate_cluster_report(self, output_file: str = None) -> str:
        """生成详细的聚类分析报告"""
        print(f"\n{'='*70}")
        print("6. 生成聚类分析报告")
        print(f"{'='*70}")

        if not output_file:
            collection_type = "slice" if self.use_slice_collection else "video"
            output_file = f"cluster_report_{collection_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        # 构建报告内容
        report_content = f"""# 聚类分析报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
集合类型: {self._get_collection_name()}
处理向量数: {self.stats['total_vectors']}
有效簇数量: {self.stats['valid_clusters']}
噪声点数量: {self.stats['noise_points']}
聚类覆盖率: {(self.stats['total_vectors'] - self.stats['noise_points']) / self.stats['total_vectors'] * 100:.1f}%

## 聚类参数
- eps: {self.cluster_eps}
- min_samples: {self.cluster_min_samples}
- 距离度量: 余弦距离

## 生成成果统计
- 因子数量: {self.stats['factors_generated']}
- 策略数量: {self.stats['strategies_generated']}
- 模板数量: {self.stats['templates_generated']}

"""

        # 添加每个簇的详细分析
        for cluster_id, analysis in self.cluster_analyses.items():
            report_content += f"\n---\n\n## 簇 {cluster_id} (样本数: {analysis['sample_count']})\n\n"

            # 添加样本示例
            report_content += "### 样本示例\n"
            for i, doc in enumerate(analysis['sample_documents'][:3]):  # 最多3个示例
                report_content += f"**示例{i+1}:**\n```\n{doc[:500]}...\n```\n\n"

            # 添加提取的因子
            factors = analysis.get('factors', [])
            if factors:
                report_content += "### 提取的共性因子\n"
                for i, factor in enumerate(factors):
                    report_content += f"#### 因子{i+1}: {factor.get('name', '未命名')}\n"
                    report_content += f"- 类型: {factor.get('factor_type', '未知')}\n"
                    report_content += f"- 描述: {factor.get('description', '无描述')}\n"
                    report_content += f"- 适用场景: {', '.join(factor.get('applicable_scenarios', []))}\n"
                    if factor.get('example'):
                        report_content += f"- 示例:\n```json\n{json.dumps(factor['example'], ensure_ascii=False, indent=2)}\n```\n"
                    report_content += "\n"

            # 添加生成的策略
            strategy = analysis.get('strategy')
            if strategy:
                report_content += "### 生成的创作策略\n"
                report_content += f"**策略名称**: {strategy.get('name', '未命名')}\n\n"
                report_content += f"**描述**: {strategy.get('description', '无描述')}\n\n"
                report_content += f"**核心逻辑**: {strategy.get('core_logic', '无')}\n\n"
                report_content += f"**必填因子类型**: {', '.join(strategy.get('required_factor_types', []))}\n\n"
                report_content += f"**可选因子类型**: {', '.join(strategy.get('optional_factor_types', []))}\n\n"
                report_content += f"**组合规则**: {strategy.get('combination_rules', '无')}\n\n"

        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"聚类报告已生成: {output_file}")
        return output_file

    def export_raw_data(self, output_file: str = None) -> str:
        """导出原始数据到JSON"""
        if not output_file:
            collection_type = "slice" if self.use_slice_collection else "video"
            output_file = f"inspiration_raw_data_{collection_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        export_data = {
            "metadata": {
                "collection": self._get_collection_name(),
                "generate_time": datetime.now().isoformat(),
                "stats": self.stats,
                "cluster_params": {
                    "eps": self.cluster_eps,
                    "min_samples": self.cluster_min_samples
                }
            },
            "clusters": self.cluster_analyses,
            "factors": [
                {
                    "factor_id": f.factor_id,
                    "factor_type": f.factor_type,
                    "name": f.name,
                    "description": f.description,
                    "tags": f.tags,
                    "popularity": float(f.popularity)
                } for f in self.factors.values()
            ],
            "strategies": [
                {
                    "strategy_id": s.strategy_id,
                    "name": s.name,
                    "core_logic": s.core_logic,
                    "success_rate": float(s.success_rate),
                    "tags": s.tags
                } for s in self.strategies.values()
            ],
            "templates": [
                {
                    "template_id": t.template_id,
                    "name": t.name,
                    "success_rate": float(t.success_rate),
                    "combination_example": t.combination_example
                } for t in self.templates
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"原始数据已导出: {output_file}")
        return output_file

async def run_full_pipeline():
    """运行完整流水线"""
    print("=" * 80)
    print("基于大模型的灵感模板生成流水线")
    print("=" * 80)

    # 第一步：处理slice_collection，生成因子
    print("\n" + ">" * 40)
    print("处理 slice_collection (生成因子)")
    print(">" * 40)

    slice_pipeline = InspirationPipelineLLM(
        use_slice_collection=True,
        max_vectors=300,
        cluster_eps=0.2,
        cluster_min_samples=3
    )
    slice_pipeline.fetch_vectors_and_documents()
    slice_pipeline.perform_clustering()
    await slice_pipeline.analyze_clusters_with_llm()
    slice_pipeline.build_models_from_analysis()
    await slice_pipeline.save_to_database()
    slice_report = slice_pipeline.generate_cluster_report()
    slice_raw_data = slice_pipeline.export_raw_data()

    # 第二步：处理video_collection，生成策略和模板
    print("\n" + ">" * 40)
    print("处理 video_collection (生成策略和模板)")
    print(">" * 40)

    video_pipeline = InspirationPipelineLLM(
        use_slice_collection=False,
        max_vectors=200,
        cluster_eps=0.25,
        cluster_min_samples=2
    )
    video_pipeline.fetch_vectors_and_documents()
    video_pipeline.perform_clustering()
    await video_pipeline.analyze_clusters_with_llm()
    video_pipeline.build_models_from_analysis()
    await video_pipeline.save_to_database()
    video_report = video_pipeline.generate_cluster_report()
    video_raw_data = video_pipeline.export_raw_data()

    # 汇总结果
    print("\n" + "=" * 80)
    print("✅ 流水线执行完成!")
    print("=" * 80)
    print("\n📊 总统计:")
    print(f"  总因子数量: {len(slice_pipeline.factors) + len(video_pipeline.factors)}")
    print(f"  总策略数量: {len(video_pipeline.strategies)}")
    print(f"  总模板数量: {len(video_pipeline.templates)}")
    print("\n📄 生成的报告:")
    print(f"  - 片段聚类报告: {slice_report}")
    print(f"  - 视频聚类报告: {video_report}")
    print("\n💾 数据文件:")
    print(f"  - 片段原始数据: {slice_raw_data}")
    print(f"  - 视频原始数据: {video_raw_data}")

if __name__ == "__main__":
    asyncio.run(run_full_pipeline())
