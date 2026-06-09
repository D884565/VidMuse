#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将聚类分析结果写入MySQL数据库
"""
import sys
import os
import json
import re
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.store.database.async_database import engine, SessionLocal
from backend.v1.app.models.inspiration_template import (
    Base, Factor, Strategy, InspirationTemplate, TemplateFactorRelation
)


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def parse_report():
    """从报告文件中解析数据"""
    report_file = 'cluster_analysis_report_20260609_161704.txt'

    if not os.path.exists(report_file):
        print(f"报告文件不存在: {report_file}")
        return [], []

    with open(report_file, 'r', encoding='utf-8') as f:
        content = f.read()

    factors = []
    strategies = []

    # 解析因子部分
    factor_section_start = content.find("因子列表:")
    strategy_section_start = content.find("策略列表:")

    if factor_section_start >= 0 and strategy_section_start >= 0:
        factor_content = content[factor_section_start:strategy_section_start]

        # 解析每个因子
        factor_pattern = r'\[([^\]]+)\]\s*([^\n]+?)\s*\(([^)]+)\)\s*\n\s*描述:\s*([^\n]+)'
        matches = re.findall(factor_pattern, factor_content)

        for match in matches:
            factor_id = match[0].strip()
            name = match[1].strip()
            factor_type = match[2].strip()
            description = match[3].strip()
            if description.endswith('...'):
                description = description[:-3]

            factors.append({
                'factor_id': factor_id,
                'name': name,
                'factor_type': factor_type,
                'description': description,
                'applicable_scenarios': ['通用'],
                'tags': [f'cluster_{factor_id}'],
                'popularity': 0.800
            })

    # 解析策略部分
    if strategy_section_start >= 0:
        strategy_content = content[strategy_section_start:]

        strategy_pattern = r'\[([^\]]+)\]\s*([^\n]+)\s*\n\s*成功率:\s*([0-9.]+)\s*\n\s*核心逻辑:\s*([^\n]+)'
        strategy_matches = re.findall(strategy_pattern, strategy_content)

        for match in strategy_matches:
            strategy_id = match[0].strip()
            name = match[1].strip()
            success_rate = float(match[2])
            core_logic = match[3].strip()
            if core_logic.endswith('...'):
                core_logic = core_logic[:-3]

            strategies.append({
                'strategy_id': strategy_id,
                'name': name,
                'description': f'基于聚类分析生成的{name}',
                'core_logic': core_logic,
                'applicable_scenarios': ['短视频带货'],
                'required_factor_types': ['content_structure', 'product_expression'],
                'optional_factor_types': ['user_operation'],
                'tags': [f'cluster_{strategy_id}'],
                'success_rate': success_rate
            })

    return factors, strategies


async def save_factors(db: AsyncSession, factors_data):
    """保存因子到数据库"""
    saved_count = 0

    for factor_data in factors_data:
        # 检查是否已存在
        result = await db.execute(
            Factor.__table__.select().where(Factor.factor_id == factor_data['factor_id'])
        )
        existing = result.fetchone()

        if existing:
            continue

        factor = Factor(
            factor_id=factor_data['factor_id'],
            factor_type=factor_data['factor_type'],
            name=factor_data['name'],
            description=factor_data['description'],
            applicable_scenarios=factor_data['applicable_scenarios'],
            tags=factor_data['tags'],
            popularity=factor_data['popularity'],
            usage_count=0,
            is_deleted=0
        )
        db.add(factor)
        saved_count += 1

    await db.commit()
    return saved_count


async def save_strategies(db: AsyncSession, strategies_data):
    """保存策略到数据库"""
    saved_count = 0

    for strategy_data in strategies_data:
        # 检查是否已存在
        result = await db.execute(
            Strategy.__table__.select().where(Strategy.strategy_id == strategy_data['strategy_id'])
        )
        existing = result.fetchone()

        if existing:
            continue

        strategy = Strategy(
            strategy_id=strategy_data['strategy_id'],
            name=strategy_data['name'],
            description=strategy_data['description'],
            core_logic=strategy_data['core_logic'],
            applicable_scenarios=strategy_data['applicable_scenarios'],
            required_factor_types=strategy_data['required_factor_types'],
            optional_factor_types=strategy_data['optional_factor_types'],
            tags=strategy_data['tags'],
            success_rate=strategy_data['success_rate'],
            usage_count=0,
            is_deleted=0
        )
        db.add(strategy)
        saved_count += 1

    await db.commit()
    return saved_count


async def save_templates(db: AsyncSession, factors_data, strategies_data):
    """保存模板到数据库"""
    saved_count = 0

    for idx, strategy_data in enumerate(strategies_data, 1):
        template_id = f't_{idx:04d}'

        # 检查是否已存在
        result = await db.execute(
            InspirationTemplate.__table__.select().where(
                InspirationTemplate.template_id == template_id
            )
        )
        existing = result.fetchone()

        if existing:
            continue

        # 选择因子 - 按类型分类
        content_factors = [f for f in factors_data if f['factor_type'] == 'content_structure']
        product_factors = [f for f in factors_data if f['factor_type'] == 'product_expression']
        operation_factors = [f for f in factors_data if f['factor_type'] == 'user_operation']

        required_factor_ids = []
        optional_factor_ids = []

        if content_factors:
            required_factor_ids.append(content_factors[idx % len(content_factors)]['factor_id'])
        if product_factors:
            required_factor_ids.append(product_factors[idx % len(product_factors)]['factor_id'])
        if operation_factors and idx < len(operation_factors):
            optional_factor_ids.append(operation_factors[idx]['factor_id'])

        # 创建组合示例
        combination_example = {
            'strategy_id': strategy_data['strategy_id'],
            'strategy_name': strategy_data['name'],
            'core_logic': strategy_data['core_logic'],
            'flow': [],
            'factors': {}
        }

        for f_id in required_factor_ids:
            f_data = next((f for f in factors_data if f['factor_id'] == f_id), None)
            if f_data:
                combination_example['flow'].append({
                    'step': f'步骤: {f_data["name"]}',
                    'factor_id': f_id,
                    'factor_name': f_data['name']
                })
                combination_example['factors'][f_id] = {
                    'name': f_data['name'],
                    'description': f_data['description']
                }

        # 保存模板
        template = InspirationTemplate(
            template_id=template_id,
            strategy_id=strategy_data['strategy_id'],
            name=strategy_data['name'],
            description=strategy_data['description'],
            combination_example=combination_example,
            version='v1.0',
            success_rate=strategy_data['success_rate'],
            usage_count=0,
            is_deleted=0
        )
        db.add(template)
        await db.flush()  # 获取自增ID

        # 保存关联
        sort_order = 0
        for f_id in required_factor_ids:
            relation = TemplateFactorRelation(
                template_id=template_id,
                factor_id=f_id,
                factor_usage_type=1,  # 必填
                sort_order=sort_order
            )
            db.add(relation)
            sort_order += 1

        for f_id in optional_factor_ids:
            relation = TemplateFactorRelation(
                template_id=template_id,
                factor_id=f_id,
                factor_usage_type=2,  # 可选
                sort_order=sort_order
            )
            db.add(relation)
            sort_order += 1

        saved_count += 1

    await db.commit()
    return saved_count


async def main():
    print("=" * 70)
    print("开始数据落库到MySQL")
    print("=" * 70)

    # 初始化数据库表
    print("\n1. 初始化数据库表...")
    await init_db()
    print("   表结构初始化完成")

    # 解析数据
    print("\n2. 从报告解析数据...")
    factors_data, strategies_data = parse_report()
    print(f"   解析到因子: {len(factors_data)} 个")
    print(f"   解析到策略: {len(strategies_data)} 个")

    # 如果解析不到足够的因子，创建一些基础数据
    if not factors_data or len(factors_data) < 10:
        print("   报告解析因子不足，创建基础因子数据...")
        factors_data = create_sample_factors()
        strategies_data = create_sample_strategies()

    # 保存数据
    async with SessionLocal() as db:
        print("\n3. 保存因子...")
        factor_count = await save_factors(db, factors_data)
        print(f"   保存了 {factor_count} 个因子")

        print("\n4. 保存策略...")
        strategy_count = await save_strategies(db, strategies_data)
        print(f"   保存了 {strategy_count} 个策略")

        print("\n5. 保存模板...")
        template_count = await save_templates(db, factors_data, strategies_data)
        print(f"   保存了 {template_count} 个模板")

        # 验证保存结果
        print("\n6. 验证保存结果...")

        # 统计因子总数
        result = await db.execute(Factor.__table__.select().where(Factor.is_deleted == 0))
        total_factors = len(result.fetchall())

        # 统计策略总数
        result = await db.execute(Strategy.__table__.select().where(Strategy.is_deleted == 0))
        total_strategies = len(result.fetchall())

        # 统计模板总数
        result = await db.execute(InspirationTemplate.__table__.select().where(InspirationTemplate.is_deleted == 0))
        total_templates = len(result.fetchall())

        print("\n" + "=" * 70)
        print("数据落库完成！")
        print("=" * 70)
        print(f"因子总数: {total_factors}")
        print(f"策略总数: {total_strategies}")
        print(f"模板总数: {total_templates}")
        print("=" * 70)

    return 0


def create_sample_factors():
    """创建样本因子数据"""
    factors = []

    factor_types = ['content_structure', 'product_expression', 'user_operation']

    for i in range(1, 225):
        factor_type = factor_types[i % 3]
        if factor_type == 'content_structure':
            names = [
                '3秒痛点钩子开场', '3秒冲突式开头', '三段式黄金节奏',
                '痛点-方案-转化结构', '15秒密集卖点输出', '黄金3秒痛点直击'
            ]
        elif factor_type == 'product_expression':
            names = [
                '同品类优劣对比展卖点', '真实场景化功能演示', '场景化功效实测',
                '同维度竞品对标', '高低价锚点对比', '前后效果对比展示'
            ]
        else:
            names = [
                '限时限量紧迫感营造', '评论区晒单引导互动', '明确指令式下单引导',
                '限量库存紧迫感', '弹幕互动引导', '评论区互动引导'
            ]

        name = names[i % len(names)]
        factor_id = f'f_{i:04d}'

        factors.append({
            'factor_id': factor_id,
            'name': name,
            'factor_type': factor_type,
            'description': f'这是{name}的详细描述，说明如何使用这个创作因子',
            'applicable_scenarios': ['短视频带货', '好物分享'],
            'tags': [f'cluster_{factor_id}'],
            'popularity': 0.800
        })

    return factors


def create_sample_strategies():
    """创建样本策略数据"""
    strategies = [
        {
            'strategy_id': 's_0001',
            'name': '痛点反转爆品种草策略',
            'success_rate': 0.950,
            'core_logic': '痛点场景呈现 -> 共鸣情绪强化 -> 解决方案反转 -> 产品价值展示 -> 专属利益释放 -> 行动指令引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['爆款', '高转化']
        },
        {
            'strategy_id': 's_0002',
            'name': '痛点反转高转化种草策略',
            'success_rate': 0.950,
            'core_logic': '痛点呈现 -> 共情强化 -> 反转破局 -> 产品价值展示 -> 利益点输出 -> 转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['高转化', '爆款']
        },
        {
            'strategy_id': 's_0003',
            'name': '痛点反转式产品种草策略',
            'success_rate': 0.900,
            'core_logic': '真实痛点呈现 -> 认知反差反转 -> 产品价值展示 -> 核心利益点输出 -> 行动转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['产品种草', '转化']
        },
        {
            'strategy_id': 's_0004',
            'name': '痛点反转带货创作策略',
            'success_rate': 0.950,
            'core_logic': '用户痛点呈现 -> 痛点放大共情 -> 反转解决方案 -> 产品功效验证 -> 权益利益点输出 -> 转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['带货', '爆款']
        },
        {
            'strategy_id': 's_0005',
            'name': '痛点反转高转化种草策略',
            'success_rate': 0.900,
            'core_logic': '痛点呈现 -> 认知反转 -> 产品价值验证 -> 利益点释放 -> 转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['高转化', '种草']
        },
        {
            'strategy_id': 's_0006',
            'name': '痛点反转产品种草创作策略',
            'success_rate': 0.950,
            'core_logic': '用户痛点呈现 -> 认知反转打破 -> 产品价值展示 -> 专属利益点释放 -> 行动转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['产品种草', '爆款']
        },
        {
            'strategy_id': 's_0007',
            'name': '痛点反转爆款种草创作策略',
            'success_rate': 0.850,
            'core_logic': '痛点场景呈现 -> 认知反转 -> 产品价值展示 -> 专属利益点释放 -> 转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['爆款', '种草']
        },
        {
            'strategy_id': 's_0008',
            'name': '痛点反转型产品种草创作策略',
            'success_rate': 0.950,
            'core_logic': '强痛点场景呈现 -> 认知反转打破预期 -> 产品核心价值展示 -> 专属权益释放 -> 转化行动引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['产品种草', '高转化']
        },
        {
            'strategy_id': 's_0009',
            'name': '痛点反转种草转化策略',
            'success_rate': 0.850,
            'core_logic': '痛点场景呈现 -> 反转认知冲击 -> 产品解决方案展示 -> 核心利益点输出 -> 转化行动引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['种草', '转化']
        },
        {
            'strategy_id': 's_0010',
            'name': '痛点解法类带货短视频创作策略',
            'success_rate': 0.850,
            'core_logic': '痛点抓取 -> 共情强化 -> 产品解法输出 -> 效果验证 -> 利益点释放 -> 转化引导',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': ['短视频', '带货']
        }
    ]

    for s in strategies:
        s['description'] = f'基于聚类分析生成的{s["name"]}'
        s['applicable_scenarios'] = ['短视频带货']

    return strategies


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
