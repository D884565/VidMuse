import pytest
import asyncio
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import (
    ChatRequest,
    ChatMessage,
    EmbeddingRequest,
    TextContent,
    ImageUnderstandingRequest,
    TextUnderstandingRequest,
    ImageGenerateRequest,
    ImageGenerateChunk,
    ImageGenerateResponse
)
from backend.providers.base import ImageCallback
from backend.framework.exceptions.exceptions import BaseAppException


class TestVolcanoLLM:
    """火山引擎大模型测试类"""

    def setup_class(self):
        """测试类初始化，创建LLM实例"""
        self.llm = VolcanoLLM(key=None, model_name=None)

    def test_chat_success(self):
        """测试对话接口成功调用"""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="你好，请介绍一下你自己，只用一句话回答")],
            max_tokens=100,
            temperature=0.7
        )

        response = self.llm.chat(request)
        print(response)
        assert response.content is not None
        assert len(response.content) > 0
        assert response.role == "assistant"
        assert response.usage is not None
        assert response.usage.total_tokens > 0

    def test_chat_param_validation_error(self):
        """测试对话接口参数验证错误"""
        with pytest.raises(BaseAppException) as exc_info:
            # temperature超出范围0-2
            ChatRequest(
                messages=[ChatMessage(role="user", content="你好")],
                temperature=3.0
            )
        assert "参数验证失败" in str(exc_info.value)

    def test_stream_chat(self):
        """测试流式对话接口"""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="请用3句话描述春天的景色")],
            stream=True,
            max_tokens=200
        )

        response_stream = self.llm.stream_chat(request)
        full_content = ""

        for chunk in response_stream:
            assert isinstance(chunk, str)
            print(chunk)
            full_content += chunk

        assert len(full_content) > 0
        assert "春天" in full_content

    def test_embedding(self):
        """测试嵌入接口"""
        request = EmbeddingRequest(
            texts=[
                TextContent(text="今天天气真好"),
                TextContent(text="我喜欢编程")
            ]
        )

        response = self.llm.embedding(request)
        print(response)

    def test_image_understanding(self):
        """测试图片理解接口"""
        # 使用公开的测试图片
        request = ImageUnderstandingRequest(
            image_url="https://picsum.photos/200/300",
            prompt="请描述这张图片的内容，只用一句话回答",
            max_tokens=100
        )

        response = self.llm.image_understanding(request)
        print(response)
        assert response.content is not None
        assert len(response.content) > 0
        assert response.usage is not None

    def test_text_understanding(self):
        """测试文本理解接口"""
        request = TextUnderstandingRequest(
            text="今天天气晴朗，阳光明媚，我和朋友一起去公园散步，玩得很开心。",
            prompt="请分析这段文本的情感倾向，只用'积极'、'消极'或'中性'回答"
        )

        response = self.llm.text_understanding(request)
        print(response)
        assert response.content is not None
        assert "积极" in response.content
        assert response.usage is not None

    def test_image_create(self):
        """测试同步图片生成接口"""
        request = ImageGenerateRequest(
            prompt="一个可爱的卡通小猫，白色背景",
            size="2048x2048",
            watermark=False
        )

        response = self.llm.image_create(request)
        print(response)
        assert response.urls is not None
        assert len(response.urls) >= 1
        assert isinstance(response.urls[0], ImageGenerateChunk)
        assert response.urls[0].url is not None
        assert response.urls[0].url.startswith("http")

    def test_image_create_stream(self):
        """测试流式图片生成接口"""
        class TestCallback(ImageCallback):
            def __init__(self):
                self.chunks = []
                self.completed = False
                self.error = None

            def on_next(self, content: ImageGenerateChunk, **kwargs) -> None:
                self.chunks.append(content)

            def on_complete(self, full: ImageGenerateResponse, **kwargs) -> None:
                self.completed = True
                self.full_response = full

            def on_error(self, exception: Exception, **kwargs) -> None:
                self.error = exception

        callback = TestCallback()

        request = ImageGenerateRequest(
            prompt="一组可爱的小狗图片",
            sequential_image_generation="auto",
            max_images=2,
            stream=True,
            watermark=False
        )

        self.llm.image_create_stream(request, callback)

        assert callback.error is None
        assert callback.completed is True
        assert len(callback.chunks) >= 1
        assert len(callback.full_response.urls) == len(callback.chunks)
        for chunk in callback.chunks:
            assert chunk.url is not None
            assert chunk.url.startswith("http")

    @pytest.mark.asyncio
    async def test_image_understanding_response(self):
        """测试异步图片理解接口"""
        request = ImageUnderstandingRequest(
            image_url="https://picsum.photos/200/300",
            prompt="请描述这张图片的内容，只用一句话回答",
            max_tokens=100
        )

        response = await self.llm.image_understanding_response(request)
        print(response)

        assert response.content is not None
        assert len(response.content) > 0
        assert response.usage is not None

    @pytest.mark.asyncio
    async def test_video_understanding(self):
        """测试异步视频理解接口（使用公开测试视频）"""
        # 使用公开的测试视频
        request = TextUnderstandingRequest(
            text="请描述这个视频的内容",
            prompt="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        )
        pytest.skip("视频理解测试需要较长时间，默认跳过")
        # response = await self.llm.video_understanding(request)
        # assert response.content is not None

    @pytest.mark.asyncio
    async def test_generate_video(self):
        """测试视频生成接口"""
        pytest.skip("视频生成测试消耗配额较多，默认跳过")
        # from backend.providers.dto.schema import VideoRequest
        # request = VideoRequest(
        #     duration=5,
        #     ratio="16:9",
        #     watermark=False
        # )
        # response = await self.llm.generate_video(request, "一只可爱的小猫在草地上奔跑", None)
        # assert response.video_url is not None
        # assert response.video_url.startswith("http")
