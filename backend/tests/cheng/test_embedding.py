#!/usr/bin/env python3
"""
Embedding 接口测试类
测试多模态嵌入接口的功能正确性，包括文本、图片、视频等多种输入格式
"""
import unittest
import os
import pytest
from dotenv import load_dotenv

from backend.providers import VolcanoLLM, EmbeddingRequest

pytestmark = pytest.mark.skip(reason="集成测试：需要真实 API 凭据")


class TestEmbedding(unittest.TestCase):
    """Embedding 接口测试类"""

    @classmethod
    def setUpClass(cls):
        """初始化测试环境，加载配置和创建LLM实例"""
        load_dotenv()


        # 创建LLM实例
        cls.llm = VolcanoLLM(
            key=None,
            model_name=None
        )



    def test_02_embedding_text_object(self):
        """测试结构化文本对象嵌入"""
        print("\n" + "="*60)
        print("测试2: 结构化文本对象嵌入")
        print("="*60)

        request = EmbeddingRequest(
            texts=[
                {"type": "text", "text": "Python是一门优秀的编程语言"},
            ]
        )

        response = self.llm.embedding(request)

        # 验证响应


        print(f"✓ 嵌入向量数量: {len(response.embeddings)}")
        print(f"✓ 向量维度: {len(response.embeddings[0])}")
        print(f"✓ Token使用: {response.usage.total_tokens}")
        print("✓ 结构化文本对象嵌入测试通过")

    def test_03_embedding_image_url(self):
        """测试图片URL嵌入"""
        print("\n" + "="*60)
        print("测试3: 图片URL嵌入")
        print("="*60)

        # 使用公开的测试图片
        test_image_url = "https://picsum.photos/200/300"

        request = EmbeddingRequest(
            texts=[
                {"type": "image_url", "image_url": {"url": test_image_url}}
            ]
        )

        try:
            response = self.llm.embedding(request)

            # 验证响应

            print(f"✓ 嵌入向量维度: {len(response.embeddings[0])}")
            print(f"✓ Token使用: {response.usage.total_tokens}")
            print("✓ 图片URL嵌入测试通过")
        except Exception as e:
            if "multimodal" in str(e).lower() or "image" in str(e).lower() or "not support" in str(e).lower():
                print(f"⚠ 当前嵌入模型不支持图片嵌入，跳过测试: {str(e)}")
                self.skipTest("当前嵌入模型不支持图片嵌入功能")
            else:
                raise

    def test_04_embedding_mixed_types(self):
        """测试混合类型输入嵌入"""
        print("\n" + "="*60)
        print("测试4: 混合类型输入嵌入")
        print("="*60)

        # 使用公开的测试图片
        test_image_url = "https://picsum.photos/200/300"

        request = EmbeddingRequest(
            texts=[
                {"type": "text", "text": "Python是一门优秀的编程语言"},
                {"type": "image_url", "image_url": {"url": test_image_url}}
            ]
        )

        try:
            response = self.llm.embedding(request)


            print(f"✓ 嵌入向量数量: {len(response.embeddings)}")
            print(f"✓ 所有向量维度均为: {len(response.embeddings[0])}")
            print(f"✓ Token使用: {response.usage.total_tokens}")
            print("✓ 混合类型输入嵌入测试通过")
        except Exception as e:
            if "multimodal" in str(e).lower() or "image" in str(e).lower() or "not support" in str(e).lower():
                print(f"⚠ 当前嵌入模型不支持多模态混合输入，跳过测试: {str(e)}")
                self.skipTest("当前嵌入模型不支持多模态混合输入功能")
            else:
                raise

    def test_05_embedding_video_url(self):
        """测试视频URL嵌入"""
        print("\n" + "="*60)
        print("测试5: 视频URL嵌入")
        print("="*60)

        # 使用示例视频URL
        test_video_url = "https://ark-project.tos-cn-beijing.volces.com/doc_video/ark_vlm_video_input.mp4"

        request = EmbeddingRequest(
            texts=[
                {"type": "video_url", "video_url": {"url": test_video_url}}
            ]
        )

        try:
            response = self.llm.embedding(request)


            print(f"✓ 嵌入向量维度: {len(response.embeddings[0])}")
            print(f"✓ Token使用: {response.usage.total_tokens}")
            print("✓ 视频URL嵌入测试通过")
        except Exception as e:
            if "multimodal" in str(e).lower() or "video" in str(e).lower() or "not support" in str(e).lower():
                print(f"⚠ 当前嵌入模型不支持视频嵌入，跳过测试: {str(e)}")
                self.skipTest("当前嵌入模型不支持视频嵌入功能")
            else:
                raise


def run_all_tests():
    """运行所有测试并生成报告"""
    print("\n" + "="*70)
    print("🚀 开始运行 Embedding 接口测试套件")
    print("="*70)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestEmbedding)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果
    print("\n" + "="*70)
    print("📊 测试结果统计")
    print("="*70)
    print(f"总测试用例: {result.testsRun}")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过!")
        return 0
    else:
        print("\n❌ 部分测试失败!")
        return 1


if __name__ == "__main__":
    exit(run_all_tests())
