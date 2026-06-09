#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库当前状态
查看已有的因子、策略、模版数据
"""
import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.v1.app.admin.inspiration_template.dao.inspiration_dao import (
    FactorDAO, StrategyDAO, InspirationTemplateDAO, TemplateFactorRelationDAO
)
from backend.store.database.async_database import get_db


async def check_database():
    print("=" * 70)
    print("检查数据库状态")
    print("=" * 70)

    db_gen = get_db()
    db = await anext(db_gen)

    try:
        print(f"\n🕐 {datetime.now().strftime('%H:%M:%S')} 正在查询数据...")

        # 查询因子
        print("\n" + "-" * 50)
        print("📦 因子 (Factors)")
        print("-" * 50)
        factor_total, factors = await FactorDAO.list_factors(db, page_size=200)
        print(f"总数: {factor_total}")
        for f in factors[:20]:  # 只显示前20个
            print(f"  [{f.factor_id}] {f.name} ({f.factor_type}) - 流行度: {f.popularity}")
        if factor_total > 20:
            print(f"  ... 还有 {factor_total - 20} 个因子")

        # 查询策略
        print("\n" + "-" * 50)
        print("🎯 策略 (Strategies)")
        print("-" * 50)
        strategy_total, strategies = await StrategyDAO.list_strategies(db, page_size=100)
        print(f"总数: {strategy_total}")
        for s in strategies:
            print(f"  [{s.strategy_id}] {s.name}")
            print(f"     成功率: {s.success_rate}")
            print(f"     必填因子类型: {s.required_factor_types}")
            print(f"     可选因子类型: {s.optional_factor_types}")

        # 查询模版
        print("\n" + "-" * 50)
        print("📝 模版 (Templates)")
        print("-" * 50)
        template_total, templates = await InspirationTemplateDAO.list_templates(db, page_size=100)
        print(f"总数: {template_total}")
        for t in templates:
            print(f"  [{t.template_id}] {t.name}")
            print(f"     关联策略: {t.strategy_id}")
            print(f"     成功率: {t.success_rate}")
            # 查询关联的因子
            relations = await TemplateFactorRelationDAO.get_relations_by_template_id(db, t.template_id)
            if relations:
                req_factors = [r.factor_id for r in relations if r.factor_usage_type == 1]
                opt_factors = [r.factor_id for r in relations if r.factor_usage_type == 2]
                print(f"     关联因子: {len(relations)} 个 (必填: {len(req_factors)}, 可选: {len(opt_factors)})")

        print("\n" + "=" * 70)
        print("📊 统计总结")
        print("=" * 70)
        print(f"因子总数: {factor_total}")
        print(f"策略总数: {strategy_total}")
        print(f"模版总数: {template_total}")

        if template_total < strategy_total:
            print(f"\n⚠️  发现: 模版数量 ({template_total}) < 策略数量 ({strategy_total})")
            print(f"需要为 {strategy_total - template_total} 个策略创建模版")
        elif template_total == 0 and strategy_total > 0:
            print(f"\n⚠️  发现: 有 {strategy_total} 个策略但没有模版")
            print("需要为所有策略创建模版")
        else:
            print(f"\n✅ 数据状态良好")

        return {
            "factor_total": factor_total,
            "strategy_total": strategy_total,
            "template_total": template_total,
            "factors": factors,
            "strategies": strategies,
            "templates": templates
        }

    finally:
        try:
            await anext(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    asyncio.run(check_database())
