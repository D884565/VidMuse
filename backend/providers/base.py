from abc import ABC, abstractmethod
from typing import Iterator, Optional
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
    ChatUsage
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

