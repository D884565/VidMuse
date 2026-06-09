#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试因子提取问题
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.v1.app.pipeline.services.llm_service import LLMService


class MockLLMService(LLMService):
    """模拟LLM服务"""

    def extract_common_factors(self, reports):
        print(f"Mock extract_common_factors called with {len(reports)} reports")
        return [
            {
                "factor_type": "content_structure",
                "name": "3秒痛点钩子开场",
                "description": "视频前3秒直接抛出目标用户高频痛点，快速抓取用户注意力",
                "applicable_scenarios": ["短视频带货"],
                "tags": ["hook", "开头"],
                "popularity": 0.9,
                "example": {"text": "test"}
            }
        ]


def test_factor_extract():
    """测试因子提取"""
    print("Testing factor extraction...")

    llm = MockLLMService()

    # 模拟报告数据
    reports = [
        {"content": "测试内容1", "hot_score": 85},
        {"content": "测试内容2", "hot_score": 85}
    ]

    result = llm.extract_common_factors(reports)
    print(f"Result: {result}")
    print(f"Type: {type(result)}")

    return 0


if __name__ == "__main__":
    sys.exit(test_factor_extract())
