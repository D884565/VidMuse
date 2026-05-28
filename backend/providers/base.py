from abc import ABC, abstractmethod
from typing import Iterator, Optional, Awaitable
from pydantic import ValidationError
from backend.framework.exceptions.exceptions import BaseAppException
from backend.framework.exceptions.error_codes import (
    AI_SERVICE_ERROR,
    PARAM_ERROR
)
from backend.providers.dto.schema import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ChatUsage,
    VideoRequest,
    VideoResponse,
    ImageUnderstandingRequest,
    ImageUnderstandingResponse,
    TextUnderstandingRequest,
    TextUnderstandingResponse,
    VideoUnderstandingRequest,
    VideoUnderstandingResponse,
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageGenerateChunk
)


class StreamChatCallback(ABC):
    """流式对话回调抽象基类，用于处理流式对话的各个阶段"""

    @abstractmethod
    def on_next(self, content: str, **kwargs) -> None:
        """
        当收到新的内容片段时调用
        :param content: 内容片段
        :param kwargs: 额外参数，如chunk原始数据等
        """
        pass

    @abstractmethod
    def on_complete(self, full_content: str, usage: Optional[ChatUsage] = None, **kwargs) -> None:
        """
        当流式对话完成时调用
        :param full_content: 完整的响应内容
        :param usage: token使用情况，部分LLM流式响应可能不返回此信息
        :param kwargs: 额外参数
        """
        pass

    @abstractmethod
    def on_error(self, exception: Exception, **kwargs) -> None:
        """
        当发生错误时调用
        :param exception: 异常对象
        :param kwargs: 额外参数
        """
        pass


class ImageCallback(ABC):
    """流式图片生成回调抽象基类，用于处理流式图片生成的各个阶段"""

    @abstractmethod
    def on_next(self, content: 'ImageGenerateChunk', **kwargs) -> None:
        """
        当收到新的图片时调用
        :param content: 图片内容片段
        :param kwargs: 额外参数，如chunk原始数据等
        """
        pass

    @abstractmethod
    def on_complete(self, full: ImageGenerateResponse, **kwargs) -> None:
        """
        当流式图片生成完成时调用
        :param full: 完整的响应内容
        :param kwargs: 额外参数
        """
        pass

    @abstractmethod
    def on_error(self, exception: Exception, **kwargs) -> None:
        """
        当发生错误时调用
        :param exception: 异常对象
        :param kwargs: 额外参数
        """
        pass


class LLMBase(ABC):
    """大模型抽象基类，定义统一的接口"""

    @abstractmethod
    def __init__(self, **kwargs):
        """
        初始化大模型客户端
        :param api_key: API密钥
        :param model: 默认模型名称
        :param kwargs: 其他配置参数
        """
        pass

    def chat(self, request: ChatRequest) -> ChatResponse:
        """
        对话接口（对外统一入口）
        :param request: 对话请求对象
        :return: 对话响应对象
        """
        try:

            # 调用具体实现
            return self._chat(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"AI服务调用失败: {str(e)}") from e

    @abstractmethod
    def _chat(self, request: ChatRequest) -> ChatResponse:
        """
        对话接口具体实现，由子类实现
        :param request: 对话请求对象
        :return: 对话响应对象
        """
        pass

    def stream_chat(self, request: ChatRequest) -> Iterator[str]:
        """
        流式对话接口（对外统一入口）
        :param request: 对话请求对象
        :return: 流式响应迭代器，返回内容片段
        """
        try:

            # 调用具体实现
            return self._stream_chat(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"AI服务流式调用失败: {str(e)}") from e

    def stream_chat_with_callback(self, request: ChatRequest, callback: StreamChatCallback) -> None:
        """
        使用回调方式的流式对话接口
        :param request: 对话请求对象
        :param callback: 回调对象，用于处理流式响应的各个阶段
        """
        full_content = ""
        try:
            # 调用具体实现获取迭代器
            for content in self._stream_chat(request):
                full_content += content
                callback.on_next(content)

            # 流式响应完成
            callback.on_complete(full_content)
        except ValidationError as e:
            exception = BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}")
            callback.on_error(exception)
            raise exception from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                callback.on_error(e)
                raise e
            exception = BaseAppException(AI_SERVICE_ERROR, message=f"AI服务流式调用失败: {str(e)}")
            callback.on_error(exception)
            raise exception from e

    @abstractmethod
    def _stream_chat(self, request: ChatRequest) -> Iterator[str]:
        """
        流式对话接口具体实现，由子类实现
        :param request: 对话请求对象
        :return: 流式响应迭代器，返回内容片段
        """
        pass

    def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        多模态嵌入接口（对外统一入口）
        :param request: 嵌入请求对象
        :return: 嵌入响应对象
        """
        try:

            # 调用具体实现
            return self._embedding(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"AI嵌入服务调用失败: {str(e)}") from e

    @abstractmethod
    def _embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        多模态嵌入接口具体实现，由子类实现
        :param request: 嵌入请求对象
        :return: 嵌入响应对象
        """
        pass

    async def generate_video(self, request: VideoRequest, prompt: str, image: str | None) -> VideoResponse:
        """
        视频生成接口（对外统一入口）
        :param request: 视频生成请求对象
        :param prompt: 视频生成提示词
        :param image: 视频生成首帧（可选）
        :return: 视频生成响应对象
        """
        try:
            # 调用具体实现
            return await self._generate_video(request, prompt, image)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"视频生成服务调用失败: {str(e)}") from e

    @abstractmethod
    async def _generate_video(self, request: VideoRequest, prompt: str, image: str | None) -> VideoResponse:
        """
        视频生成接口具体实现，由子类实现
        :param request: 视频生成请求对象
        :param prompt: 视频生成提示词
        :param image: 视频生成首帧（可选）
        :return: 视频生成响应对象
        """
        pass

    def image_understanding(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口（对外统一入口）
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        try:
            # 调用具体实现
            return self._image_understanding(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"图片理解服务调用失败: {str(e)}") from e

    @abstractmethod
    def _image_understanding(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口具体实现，由子类实现
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        pass

    async def image_understanding_response(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口(responses版，对外统一入口)
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        try:
            # 调用具体实现
            return await self._image_understanding_response(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"图片理解服务调用失败: {str(e)}") from e

    @abstractmethod
    async def _image_understanding_response(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口(responses版)具体实现，由子类实现
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        pass

    def text_understanding(self, request: TextUnderstandingRequest) -> TextUnderstandingResponse:
        """
        文本理解接口（对外统一入口）
        :param request: 文本理解请求对象
        :return: 文本理解响应对象
        """
        try:
            # 调用具体实现
            return self._text_understanding(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"文本理解服务调用失败: {str(e)}") from e

    @abstractmethod
    def _text_understanding(self, request: TextUnderstandingRequest) -> TextUnderstandingResponse:
        """
        文本理解接口具体实现，由子类实现
        :param request: 文本理解请求对象
        :return: 文本理解响应对象
        """
        pass

    async def video_understanding_response(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口(responses版，对外统一入口)
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        """
        try:
            # 调用具体实现
            return await self._video_understanding_response(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"视频理解服务调用失败: {str(e)}") from e

    @abstractmethod
    async def _video_understanding_response(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口(responses版)具体实现，由子类实现
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        """
        pass

    async def video_understanding(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口（对外统一入口）
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        """
        try:
            # 调用具体实现
            return await self._video_understanding(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"视频理解服务调用失败: {str(e)}") from e

    @abstractmethod
    async def _video_understanding(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口具体实现，由子类实现
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        """
        pass

    async def video_understanding_response_file(self, request: VideoUnderstandingRequest) -> None:
        """
        视频理解接口（文件处理版，对外统一入口）
        :param request: 视频理解请求对象
        """
        try:
            # 调用具体实现
            await self._video_understanding_response_file(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"视频理解服务调用失败: {str(e)}") from e

    @abstractmethod
    async def _video_understanding_response_file(self, request: VideoUnderstandingRequest) -> None:
        """
        视频理解接口（文件处理版）具体实现，由子类实现
        :param request: 视频理解请求对象
        """
        pass

    def image_create_stream(self, request: ImageGenerateRequest, callback: ImageCallback) -> None:
        """
        流式图片生成接口（对外统一入口）
        :param request: 图片生成请求对象
        :param callback: 回调对象，用于处理流式响应的各个阶段
        """
        try:
            # 调用具体实现
            self._image_create_stream(request, callback)
        except ValidationError as e:
            exception = BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}")
            callback.on_error(exception)
            raise exception from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                callback.on_error(e)
                raise e
            exception = BaseAppException(AI_SERVICE_ERROR, message=f"图片生成服务调用失败: {str(e)}")
            callback.on_error(exception)
            raise exception from e

    @abstractmethod
    def _image_create_stream(self, request: ImageGenerateRequest, callback: ImageCallback) -> None:
        """
        流式图片生成接口具体实现，由子类实现
        :param request: 图片生成请求对象
        :param callback: 回调对象，用于处理流式响应的各个阶段
        """
        pass

    def image_create(self, request: ImageGenerateRequest) -> ImageGenerateResponse:
        """
        同步图片生成接口（对外统一入口）
        :param request: 图片生成请求对象
        :return: 图片生成响应对象
        """
        try:
            # 调用具体实现
            return self._image_create(request)
        except ValidationError as e:
            raise BaseAppException(PARAM_ERROR, message=f"参数验证失败: {str(e)}") from e
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            raise BaseAppException(AI_SERVICE_ERROR, message=f"图片生成服务调用失败: {str(e)}") from e

    @abstractmethod
    def _image_create(self, request: ImageGenerateRequest) -> ImageGenerateResponse:
        """
        同步图片生成接口具体实现，由子类实现
        :param request: 图片生成请求对象
        :return: 图片生成响应对象
        """
        pass

