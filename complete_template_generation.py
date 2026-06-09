#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成模版生成任务
从数据库读取已有的因子和策略，为每个策略生成对应的模版
"""
import sys
import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.v1.app.models.inspiration_template import Factor, Strategy, InspirationTemplate
from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO, TemplateFactorRelationDAO
)
from backend.store.database.async_database import get_db


class TemplateCompletionManager:
    """模版生成完成管理器"""

    def __init__(self):
        self.factors: Dict[str, Factor] = {}
        self.strategies: Dict[str, Strategy] = {}
        self.templates: List[Dict[str, Any]] = []
        self.stats = {
            "total_factors": 0,
            "total_strategies": 0,
            "existing_templates": 0,
            "new_templates_created": 0,
            "skipped_strategies": 0
        }

    async def load_all_data(self):
        """从数据库加载所有因子和策略"""
        print("=" * 70)
        print("第一步：从数据库加载数据")
        print("=" * 70)

        db_gen = get_db()
        db = await anext(db_gen)

        try:
            # 加载所有因子
            print("\n正在加载所有因子...")
            factor_count = 0
            page = 1
            page_size = 100

            while True:
                total, factors = await FactorDAO.list_factors(db, page=page, page_size=page_size)
                if not factors:
                    break
                for factor in factors:
                    self.factors[factor.factor_id] = factor
                    factor_count += 1
                if len(factors) < page_size:
                    break
                page += 1

            self.stats["total_factors"] = factor_count
            print(f"✅ 已加载 {factor_count} 个因子")

            # 加载所有策略
            print("\n正在加载所有策略...")
            strategy_count = 0
            page = 1

            while True:
                total, strategies = await StrategyDAO.list_strategies(db, page=page, page_size=page_size)
                if not strategies:
                    break
                for strategy in strategies:
                    self.strategies[strategy.strategy_id] = strategy
                    strategy_count += 1
                if len(strategies) < page_size:
                    break
                page += 1

            self.stats["total_strategies"] = strategy_count
            print(f"✅ 已加载 {strategy_count} 个策略")

            # 检查已有模版
            print("\n正在检查已有模版...")
            template_count = 0
            page = 1

            while True:
                total, templates = await InspirationTemplateDAO.list_templates(db, page=page, page_size=page_size)
                if not templates:
                    break
                template_count += len(templates)
                if len(templates) < page_size:
                    break
                page += 1

            self.stats["existing_templates"] = template_count
            print(f"✅ 已存在 {template_count} 个模版")

        finally:
            try:
                await anext(db_gen)
            except StopIteration:
                pass

    def get_factors_by_types(self, factor_types: List[str]) -> List[Factor]:
        """根据因子类型获取匹配的因子"""
        matched = []
        for factor_id, factor in self.factors.items():
            if factor.factor_type in factor_types:
                matched.append(factor)
        return matched

    async def generate_templates_for_strategies(self):
        """为每个策略生成模版"""
        print("\n" + "=" * 70)
        print("第二步：为策略生成模版")
        print("=" * 70)

        db_gen = get_db()
        db = await anext(db_gen)

        template_counter = self.stats["existing_templates"] + 1

        try:
            for strategy_id, strategy in self.strategies.items():
                # 检查该策略是否已有模版
                existing_count, _ = await InspirationTemplateDAO.list_templates(
                    db, strategy_id=strategy_id, page_size=100
                )

                if existing_count > 0:
                    print(f"\n跳过策略 {strategy.name} (ID: {strategy_id}) - 已有 {existing_count} 个模版")
                    self.stats["skipped_strategies"] += 1
                    continue

                print(f"\n处理策略: {strategy.name} (ID: {strategy_id})")

                # 获取必填因子
                required_factor_types = strategy.required_factor_types or ["content_structure"]
                required_factors = []

                for factor_type in required_factor_types:
                    type_factors = self.get_factors_by_types([factor_type])
                    if type_factors:
                        # 选择流行度最高的
                        type_factors.sort(key=lambda f: f.popularity, reverse=True)
                        required_factors.append(type_factors[0])
                        print(f"  选择必填因子: {type_factors[0].name} (类型: {factor_type})")

                # 如果没有匹配的必填因子，从所有因子中选择
                if not required_factors:
                    all_factors = list(self.factors.values())
                    if all_factors:
                        all_factors.sort(key=lambda f: f.popularity, reverse=True)
                        required_factors.append(all_factors[0])
                        print(f"  从全局选择必填因子: {all_factors[0].name}")

                if not required_factors:
                    print(f"  ⚠️  没有可用的因子，跳过此策略")
                    self.stats["skipped_strategies"] += 1
                    continue

                # 获取可选因子
                optional_factor_types = strategy.optional_factor_types or []
                optional_factors = []

                for factor_type in optional_factor_types[:3]:  # 最多3个可选因子
                    type_factors = self.get_factors_by_types([factor_type])
                    if type_factors:
                        type_factors.sort(key=lambda f: f.popularity, reverse=True)
                        # 避免重复
                        if type_factors[0] not in required_factors:
                            optional_factors.append(type_factors[0])
                            print(f"  选择可选因子: {type_factors[0].name} (类型: {factor_type})")

                # 生成组合示例
                combination_example = self._generate_combination_example(
                    strategy, required_factors, optional_factors
                )

                # 创建模版
                template_id = f"t_{template_counter:04d}"
                template_counter += 1

                template_data = {
                    "template_id": template_id,
                    "strategy_id": strategy.strategy_id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "combination_example": combination_example,
                    "version": "v1.0",
                    "success_rate": strategy.success_rate,
                    "usage_count": 0
                }

                # 保存模版
                template = await InspirationTemplateDAO.create_template(db, template_data)

                # 保存因子关联
                relations = []
                for idx, factor in enumerate(required_factors):
                    relations.append({
                        "template_id": template_id,
                        "factor_id": factor.factor_id,
                        "factor_usage_type": 1,  # 必填
                        "sort_order": idx
                    })

                for idx, factor in enumerate(optional_factors):
                    relations.append({
                        "template_id": template_id,
                        "factor_id": factor.factor_id,
                        "factor_usage_type": 2,  # 可选
                        "sort_order": len(required_factors) + idx
                    })

                if relations:
                    await TemplateFactorRelationDAO.batch_create_relations(db, relations)

                self.stats["new_templates_created"] += 1
                self.templates.append({
                    "template_id": template_id,
                    "strategy_id": strategy.strategy_id,
                    "name": strategy.name,
                    "required_factors": [f.factor_id for f in required_factors],
                    "optional_factors": [f.factor_id for f in optional_factors],
                    "success_rate": float(strategy.success_rate)
                })

                print(f"  ✅ 已创建模版: {template_id}")
                print(f"     必填因子: {len(required_factors)} 个")
                print(f"     可选因子: {len(optional_factors)} 个")

            await db.commit()

        except Exception as e:
            await db.rollback()
            print(f"❌ 生成模版失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            try:
                await anext(db_gen)
            except StopIteration:
                pass

    def _generate_combination_example(self, strategy: Strategy,
                                     required_factors: List[Factor],
                                     optional_factors: List[Factor]) -> Dict[str, Any]:
        """生成组合示例"""
        flow = []

        for idx, factor in enumerate(required_factors):
            flow.append({
                "step": f"步骤{idx + 1}: {factor.name}",
                "factor_id": factor.factor_id,
                "factor_name": factor.name,
                "factor_type": factor.factor_type,
                "example": factor.example or {}
            })

        for idx, factor in enumerate(optional_factors):
            flow.append({
                "step": f"可选步骤{idx + 1}: {factor.name}",
                "factor_id": factor.factor_id,
                "factor_name": factor.name,
                "factor_type": factor.factor_type,
                "example": factor.example or {}
            })

        # 构建因子映射
        factors_map = {}
        for factor in required_factors + optional_factors:
            factors_map[factor.factor_id] = {
                "name": factor.name,
                "type": factor.factor_type,
                "description": factor.description,
                "example": factor.example or {}
            }

        return {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.name,
            "core_logic": strategy.core_logic,
            "flow": flow,
            "factors": factors_map
        }

    def generate_final_report(self, output_file: str = None) -> str:
        """生成最终报告"""
        if not output_file:
            output_file = f"final_cluster_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("📊 聚类分析最终完成报告\n")
            f.write("=" * 70 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("📈 总体统计\n")
            f.write("-" * 50 + "\n")
            f.write(f"✅ 因子总数: {self.stats['total_factors']}\n")
            f.write(f"✅ 策略总数: {self.stats['total_strategies']}\n")
            f.write(f"✅ 原有模版数: {self.stats['existing_templates']}\n")
            f.write(f"🆕 新建模版数: {self.stats['new_templates_created']}\n")
            f.write(f"⏭️  跳过策略数: {self.stats['skipped_strategies']}\n")
            f.write(f"🎯 总模版数: {self.stats['existing_templates'] + self.stats['new_templates_created']}\n\n")

            if self.templates:
                f.write("\n📝 新建模版详情\n")
                f.write("-" * 50 + "\n")
                for idx, template in enumerate(self.templates, 1):
                    f.write(f"\n{idx}. [{template['template_id']}] {template['name']}\n")
                    f.write(f"   关联策略: {template['strategy_id']}\n")
                    f.write(f"   成功率: {template['success_rate']:.2f}\n")
                    f.write(f"   必填因子: {', '.join(template['required_factors'])}\n")
                    if template['optional_factors']:
                        f.write(f"   可选因子: {', '.join(template['optional_factors'])}\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write("🎉 任务全部完成！\n")
            f.write("=" * 70 + "\n")

        return output_file


async def main():
    print("=" * 70)
    print("模版生成完成工具")
    print("=" * 70)

    manager = TemplateCompletionManager()

    # 1. 加载数据
    await manager.load_all_data()

    # 2. 生成模版
    await manager.generate_templates_for_strategies()

    # 3. 生成报告
    report_file = manager.generate_final_report()

    print("\n" + "=" * 70)
    print("✅ 模版生成完成！")
    print(f"📝 最终报告: {report_file}")
    print("=" * 70)

    print(f"\n📊 总结:")
    print(f"   因子总数: {manager.stats['total_factors']}")
    print(f"   策略总数: {manager.stats['total_strategies']}")
    print(f"   新建模版: {manager.stats['new_templates_created']}")
    print(f"   总模版数: {manager.stats['existing_templates'] + manager.stats['new_templates_created']}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
