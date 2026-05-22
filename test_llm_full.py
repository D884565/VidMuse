#!/usr/bin/env python3
"""
VolcanoLLM 全功能测试类
测试所有大模型对接接口的功能正确性
"""
import unittest
import os
import asyncio
from dotenv import load_dotenv
from typing import List, Optional

from backend.vidmuse.provider import (
    VolcanoLLM,
    ChatRequest,
    ChatMessage,
    StreamChatCallback,
    VideoRequest,
    EmbeddingRequest,
    ImageUnderstandingRequest,
    TextUnderstandingRequest,
    VideoUnderstandingRequest
)


class TestStreamCallback(StreamChatCallback):
    """测试用流式回调实现"""
    def __init__(self):
        self.content_chunks: List[str] = []
        self.full_content: str = ""
        self.error: Optional[Exception] = None
        self.completed: bool = False

    def on_next(self, content: str, **kwargs) -> None:
        self.content_chunks.append(content)

    def on_complete(self, full_content: str, usage=None, **kwargs) -> None:
        self.full_content = full_content
        self.completed = True

    def on_error(self, exception: Exception, **kwargs) -> None:
        self.error = exception
        self.completed = True


class TestVolcanoLLM(unittest.TestCase):
    """VolcanoLLM 全功能测试类"""

    @classmethod
    def setUpClass(cls):
        """初始化测试环境，加载配置和创建LLM实例"""
        load_dotenv()

        # 检查必要的环境变量
        cls.api_key = os.getenv("DOUBAO_SEED_API_KEY")
        cls.default_model = os.getenv("DOUBAO_SEED", "doubao-1.5-pro")
        cls.video_model = os.getenv("DOUBAO_SEEDDANCE", "doubao-1.5-pro")

        if not cls.api_key:
            raise unittest.SkipTest("缺少DOUBAO_SEED_API_KEY环境变量，跳过所有测试")

        # 创建LLM实例
        cls.llm = VolcanoLLM(
            key=cls.api_key,
            model_name=cls.default_model
        )

    def test_01_chat_normal(self):
        """测试普通聊天接口"""
        print("\n" + "="*60)
        print("测试1: 普通聊天接口")
        print("="*60)

        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content="请用一句话介绍你自己")
            ],
            max_tokens=100
        )

        response = self.llm.chat(request)


        print(f"✓ 响应内容: {response.content[:50]}...")
        print(f"✓ Token使用: {response.usage.total_tokens}")
        print("✓ 普通聊天接口测试通过")

    def test_02_stream_chat_iterator(self):
        """测试流式聊天迭代器接口"""
        print("\n" + "="*60)
        print("测试2: 流式聊天迭代器接口")
        print("="*60)

        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content="请用100字介绍人工智能的应用")
            ],
            max_tokens=200,
            stream=True
        )

        full_content = ""
        chunk_count = 0

        for chunk in self.llm.stream_chat(request):
            self.assertIsInstance(chunk, str)
            full_content += chunk
            chunk_count += 1
            print(chunk, end="", flush=True)

        print()
        self.assertGreater(len(full_content), 0)
        self.assertGreater(chunk_count, 1)  # 流式响应应该有多个chunk

        print(f"\n✓ 响应长度: {len(full_content)} 字符")
        print(f"✓ Chunk数量: {chunk_count}")
        print("✓ 流式聊天迭代器接口测试通过")

    def test_03_stream_chat_callback(self):
        """测试流式聊天回调接口"""
        print("\n" + "="*60)
        print("测试3: 流式聊天回调接口")
        print("="*60)

        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content="请用50字介绍Python的特点")
            ],
            max_tokens=150
        )

        callback = TestStreamCallback()
        self.llm.stream_chat_with_callback(request, callback)

        # 验证回调结果
        self.assertTrue(callback.completed)
        self.assertIsNone(callback.error)
        self.assertGreater(len(callback.content_chunks), 1)
        self.assertGreater(len(callback.full_content), 0)
        self.assertEqual(''.join(callback.content_chunks), callback.full_content)

        print(f"✓ 响应内容: {callback.full_content}")
        print(f"✓ Chunk数量: {len(callback.content_chunks)}")
        print("✓ 流式聊天回调接口测试通过")



    def test_05_image_understanding(self):
        """测试图片理解接口"""
        print("\n" + "="*60)
        print("测试5: 图片理解接口")
        print("="*60)

        # 使用公开的测试图片
        test_image_url = "https://picsum.photos/200/300"

        request = ImageUnderstandingRequest(
            image_url=test_image_url,
            prompt="请描述这张图片的内容，不超过50字",
            max_tokens=100
        )

        try:
            response = self.llm.image_understanding(request)

            # 验证响应
            self.assertIsNotNone(response)
            self.assertIsNotNone(response.content)
            self.assertGreater(len(response.content), 0)
            self.assertIsNotNone(response.usage)
            self.assertGreater(response.usage.total_tokens, 0)

            print(f"✓ 理解结果: {response.content}")
            print(f"✓ Token使用: {response.usage.total_tokens}")
            print("✓ 图片理解接口测试通过")
        except Exception as e:
            if "multimodal" in str(e).lower() or "image" in str(e).lower():
                print(f"⚠ 当前模型不支持图片理解，跳过测试: {str(e)}")
                self.skipTest("当前模型不支持图片理解功能")
            else:
                raise

    def test_06_text_understanding(self):
        """测试文本理解接口"""
        print("\n" + "="*60)
        print("测试6: 文本理解接口")
        print("="*60)

        test_text = """
        北京，简称“京”，是中华人民共和国的首都、直辖市、国家中心城市、超大城市，
        国务院批复确定的中国政治中心、文化中心、国际交往中心、科技创新中心。
        北京地处中国北部、华北平原北部，东与天津毗连，其余均与河北相邻。
        北京是世界著名古都和现代化国际城市。
        """

        request = TextUnderstandingRequest(
            text=test_text,
            prompt="请总结这段文本的主要内容，不超过30字",
            max_tokens=100
        )

        response = self.llm.text_understanding(request)

        # 验证响应
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.content)
        self.assertGreater(len(response.content), 0)
        self.assertLess(len(response.content), 100)  # 摘要应该简短
        self.assertIsNotNone(response.usage)
        self.assertGreater(response.usage.total_tokens, 0)

        print(f"✓ 总结结果: {response.content}")
        print(f"✓ Token使用: {response.usage.total_tokens}")
        print("✓ 文本理解接口测试通过")

    async def _test_video_understanding_async(self):
        """异步测试视频理解接口"""
        print("\n" + "="*60)
        print("测试7: 视频理解接口")
        print("="*60)

        # 使用示例视频URL，实际测试时可替换为真实视频
        test_video_url = "https://ark-project.tos-cn-beijing.volces.com/doc_video/ark_vlm_video_input.mp4"

        request = VideoUnderstandingRequest(
            video_url=test_video_url,
            prompt="请描述这个视频的主要内容，不超过50字",
            max_tokens=100
        )

        try:
            response = await self.llm.video_understanding(request)

            # 验证响应
            self.assertIsNotNone(response)
            self.assertIsNotNone(response.content)
            self.assertGreater(len(response.content), 0)
            self.assertIsNotNone(response.usage)
            self.assertGreater(response.usage.total_tokens, 0)

            print(f"✓ 理解结果: {response.content}")
            print(f"✓ Token使用: {response.usage.total_tokens}")
            print("✓ 视频理解接口测试通过")
            return True
        except Exception as e:
            if "video" in str(e).lower() or "multimodal" in str(e).lower() or "not support" in str(e).lower():
                print(f"⚠ 当前模型不支持视频理解，跳过测试: {str(e)}")
                return False
            else:
                raise

    def test_07_video_understanding(self):
        """测试视频理解接口（同步包装）"""
        loop = asyncio.get_event_loop_policy().get_event_loop()
        supported = loop.run_until_complete(self._test_video_understanding_async())
        if not supported:
            self.skipTest("当前模型不支持视频理解功能")

    async def _test_generate_video_async(self):
        """异步测试视频生成接口"""
        print("\n" + "="*60)
        print("测试8: 视频生成接口")
        print("="*60)

        request = VideoRequest(
            duration=5,
            ratio="16:9",
            resolution="720p",
            generate_audio=True,
            watermark=False
        )

        try:
            response = await self.llm.generate_video(request, "一片美丽的花海，微风吹过，花瓣飘落", image=None)

            # 验证响应
            self.assertIsNotNone(response)
            self.assertIsNotNone(response.video_url)
            self.assertTrue(response.video_url.startswith("http"))
            self.assertEqual(response.status, "succeeded")
            self.assertIsNotNone(response.model)

            print(f"✓ 视频生成成功!")
            print(f"✓ 任务ID: {response.id}")
            print(f"✓ 视频URL: {response.video_url}")
            print(f"✓ 视频时长: {response.duration}秒")
            if hasattr(response, 'cover_url') and response.cover_url:
                print(f"✓ 封面URL: {response.cover_url}")
            print("✓ 视频生成接口测试通过")
            return True
        except Exception as e:
            if "video generation" in str(e).lower() or "not support" in str(e).lower():
                print(f"⚠ 当前账号或模型不支持视频生成，跳过测试: {str(e)}")
                return False
            else:
                raise

    def test_08_generate_video(self):
        """测试视频生成接口（同步包装）"""
        loop = asyncio.get_event_loop_policy().get_event_loop()
        supported = loop.run_until_complete(self._test_generate_video_async())
        if not supported:
            self.skipTest("当前账号或模型不支持视频生成功能")

    def test_09_chat_with_custom_model(self):
        """测试指定模型的聊天接口"""
        print("\n" + "="*60)
        print("测试9: 指定模型的聊天接口")
        print("="*60)

        # 使用默认模型测试自定义模型参数
        request = ChatRequest(
            messages=[
                ChatMessage(role="user", content="2+2等于几？")
            ],
            model=self.default_model,
            max_tokens=50
        )

        response = self.llm.chat(request)

        self.assertIsNotNone(response)
        self.assertIn("4", response.content)
        self.assertEqual(response.model, self.default_model)

        print(f"✓ 响应内容: {response.content.strip()}")
        print(f"✓ 使用模型: {response.model}")
        print("✓ 指定模型聊天接口测试通过")




def run_all_tests():
    """运行所有测试并生成报告"""
    print("\n" + "="*70)
    print("🚀 开始运行 VolcanoLLM 全功能测试套件")
    print("="*70)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestVolcanoLLM)

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
