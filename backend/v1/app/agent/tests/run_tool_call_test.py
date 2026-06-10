#!/usr/bin/env python3
"""
ScriptAgent工具调用测试运行脚本
使用方法: python run_tool_call_test.py [测试名称]
如果不指定测试名称，默认运行所有测试
"""
import os
import sys
import argparse
import unittest
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

def main():
    parser = argparse.ArgumentParser(description="运行ScriptAgent工具调用测试")
    parser.add_argument("test_name", nargs="?", help="要运行的测试名称，例如: test_auto_mode_basic_generation")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细输出")
    args = parser.parse_args()

    # 检查环境变量
    required_env = ["DOUBAO_SEED", "DOUBAO_API_KEY", "DOUBAO_API_URL"]
    missing = [var for var in required_env if not os.getenv(var)]
    if missing:
        print("❌ 缺少必要的环境变量，请在.env文件中配置:")
        for var in missing:
            print(f"   - {var}")
        print("\n配置示例:")
        print("DOUBAO_SEED=doubao-seed")
        print("DOUBAO_API_KEY=your_api_key_here")
        print("DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3")
        return 1

    # 导入测试类
    from test_script_agent_tool_calling import TestScriptAgentToolCalling

    # 创建测试套件
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    if args.test_name:
        # 运行指定测试
        suite.addTest(TestScriptAgentToolCalling(args.test_name))
    else:
        # 运行所有测试
        suite.addTests(loader.loadTestsFromTestCase(TestScriptAgentToolCalling))

    # 运行测试
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    # 输出结果
    print("\n" + "="*80)
    print(f"测试完成: 运行 {result.testsRun} 个测试，失败 {len(result.failures)} 个，错误 {len(result.errors)} 个")
    print("="*80)

    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test._testMethodName}: {traceback.splitlines()[-1]}")

    if result.errors:
        print("\n❌ 错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test._testMethodName}: {traceback.splitlines()[-1]}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
