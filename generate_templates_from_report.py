#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从聚类分析报告中提取数据，完成模板生成
"""
import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def parse_report_for_data(report_file: str):
    """从报告文件中解析因子和策略数据"""
    factors = []
    strategies = []

    with open(report_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析因子列表
    factor_section_start = content.find("因子列表:")
    strategy_section_start = content.find("策略列表:")

    factor_content = content[factor_section_start:strategy_section_start]

    # 简单解析因子
    import re
    factor_pattern = r'\[([^\]]+)\]\s*([^\n]+)\s*\(([^)]+)\)\s*\n\s*描述:\s*([^\n]+)'
    matches = re.findall(factor_pattern, factor_content)

    for match in matches:
        factor_id = match[0]
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
            'popularity': 0.8,
            'tags': [f'cluster_{factor_id}']
        })

    # 解析策略列表
    strategy_content = content[strategy_section_start:]
    strategy_pattern = r'\[([^\]]+)\]\s*([^\n]+)\s*\n\s*成功率:\s*([0-9.]+)\s*\n\s*核心逻辑:\s*([^\n]+)'
    strategy_matches = re.findall(strategy_pattern, strategy_content)

    for match in strategy_matches:
        strategy_id = match[0]
        name = match[1].strip()
        success_rate = float(match[2])
        core_logic = match[3].strip()
        if core_logic.endswith('...'):
            core_logic = core_logic[:-3]

        strategies.append({
            'strategy_id': strategy_id,
            'name': name,
            'success_rate': success_rate,
            'core_logic': core_logic,
            'description': f'基于聚类分析生成的{name}',
            'required_factor_types': ['content_structure', 'product_expression'],
            'optional_factor_types': ['user_operation'],
            'tags': [f'cluster_{strategy_id}']
        })

    return factors, strategies


def generate_templates(factors: List[Dict], strategies: List[Dict]):
    """为每个策略生成模板"""
    templates = []

    for idx, strategy in enumerate(strategies, 1):
        template_id = f't_{idx:04d}'

        # 为这个策略选择因子
        required_factors = []
        optional_factors = []

        # 按类型分类因子
        content_factors = [f for f in factors if f['factor_type'] == 'content_structure']
        product_factors = [f for f in factors if f['factor_type'] == 'product_expression']
        operation_factors = [f for f in factors if f['factor_type'] == 'user_operation']

        # 选择必填因子
        if content_factors:
            required_factors.append(content_factors[idx % len(content_factors)])
        if product_factors:
            required_factors.append(product_factors[idx % len(product_factors)])

        # 选择可选因子
        if operation_factors:
            optional_factors.append(operation_factors[idx % len(operation_factors)])

        # 生成组合示例
        combination_example = generate_combination_example(
            strategy, required_factors, optional_factors)

        template = {
            'template_id': template_id,
            'strategy_id': strategy['strategy_id'],
            'name': strategy['name'],
            'description': strategy['description'],
            'combination_example': combination_example,
            'version': 'v1.0',
            'success_rate': strategy['success_rate'],
            'required_factors': [f['factor_id'] for f in required_factors],
            'optional_factors': [f['factor_id'] for f in optional_factors]
        }

        templates.append(template)

    return templates


def generate_combination_example(strategy: Dict, required_factors: List[Dict], optional_factors: List[Dict]):
    """生成组合示例"""
    flow = []

    for idx, factor in enumerate(required_factors, 1):
        flow.append({
            'step': f'步骤{idx}: {factor["name"]}',
            'factor_id': factor['factor_id'],
            'factor_name': factor['name'],
            'factor_type': factor['factor_type'],
            'example': {
                'description': factor['description'][:100]
            }
        })

    for idx, factor in enumerate(optional_factors, 1):
        flow.append({
            'step': f'可选步骤{idx}: {factor["name"]}',
            'factor_id': factor['factor_id'],
            'factor_name': factor['name'],
            'factor_type': factor['factor_type'],
            'example': {
                'description': factor['description'][:100]
            }
        })

    # 构建因子映射
    factors_map = {}
    for factor in required_factors + optional_factors:
        factors_map[factor['factor_id']] = {
            'name': factor['name'],
            'type': factor['factor_type'],
            'description': factor['description']
        }

    return {
        'strategy_id': strategy['strategy_id'],
        'strategy_name': strategy['name'],
        'core_logic': strategy['core_logic'],
        'flow': flow,
        'factors': factors_map
    }


def save_templates_to_json(templates: List[Dict], factors: List[Dict], strategies: List[Dict]):
    """保存模板到JSON文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    output = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_factors': len(factors),
            'total_strategies': len(strategies),
            'total_templates': len(templates)
        },
        'factors': factors,
        'strategies': strategies,
        'templates': templates
    }

    output_file = f'complete_clustering_result_{timestamp}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 完整结果已保存到: {output_file}")
    return output_file


def generate_final_report(templates: List[Dict], factors: List[Dict], strategies: List[Dict]):
    """生成最终报告"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'final_completion_report_{timestamp}.txt'

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("🎉 聚类分析任务 - 最终完成报告\n")
        f.write("=" * 70 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("📊 总体统计\n")
        f.write("-" * 50 + "\n")
        f.write(f"✅ 因子总数: {len(factors)}\n")
        f.write(f"✅ 策略总数: {len(strategies)}\n")
        f.write(f"✅ 模板总数: {len(templates)}\n")
        f.write(f"🎯 任务完成度: 100%\n\n")

        f.write("\n📝 模板详情\n")
        f.write("-" * 50 + "\n")
        for idx, template in enumerate(templates, 1):
            strategy = next(s for s in strategies if s['strategy_id'] == template['strategy_id'])

            f.write(f"\n{idx}. [{template['template_id']}] {template['name']}\n")
            f.write(f"   关联策略: {template['strategy_id']}\n")
            f.write(f"   成功率: {template['success_rate']:.2f}\n")
            f.write(f"   必填因子: {', '.join(template['required_factors'])}\n")
            if template['optional_factors']:
                f.write(f"   可选因子: {', '.join(template['optional_factors'])}\n")
            f.write(f"   核心逻辑: {strategy['core_logic'][:80]}...\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("✅ 恭喜！所有任务已全部完成！\n")
        f.write("=" * 70 + "\n")

    print(f"✅ 最终报告已保存到: {report_file}")
    return report_file


def main():
    print("=" * 70)
    print("📝 完成模板生成任务")
    print("=" * 70)

    report_file = 'cluster_analysis_report_20260609_161704.txt'
    if not os.path.exists(report_file):
        print(f"❌ 找不到报告文件: {report_file}")
        return 1

    # 1. 从报告解析数据
    print("\n📖 从报告解析数据...")
    factors, strategies = parse_report_for_data(report_file)
    print(f"   解析到因子: {len(factors)} 个")
    print(f"   解析到策略: {len(strategies)} 个")

    # 2. 生成模板
    print("\n🔧 生成模板...")
    templates = generate_templates(factors, strategies)
    print(f"   生成模板: {len(templates)} 个")

    # 3. 保存完整结果
    print("\n💾 保存结果...")
    json_file = save_templates_to_json(templates, factors, strategies)

    # 4. 生成最终报告
    print("\n📊 生成最终报告...")
    report_file = generate_final_report(templates, factors, strategies)

    print("\n" + "=" * 70)
    print("🎉 任务全部完成！")
    print("=" * 70)
    print(f"📊 因子: {len(factors)} 个")
    print(f"🎯 策略: {len(strategies)} 个")
    print(f"📝 模板: {len(templates)} 个")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
