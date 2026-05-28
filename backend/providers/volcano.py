import asyncio
import os
from abc import ABC, abstractmethod
from typing import Iterator, Optional

from dotenv import load_dotenv
from openai.resources.chat.completions import messages
from volcenginesdkarkruntime import Ark, AsyncArk
from volcenginesdkarkruntime.types.images import SequentialImageGenerationOptions
from volcenginesdkcore.rest import ApiException
from backend.framework.exceptions.exceptions import BaseAppException
from backend.framework.exceptions.error_codes import (
    AI_SERVICE_ERROR,
    AI_GENERATE_FAILED,
    AI_CONTENT_VIOLATION,
    AI_QUOTA_EXHAUSTED,
    THIRD_PARTY_TIMEOUT
)

from backend.providers.base import LLMBase, ImageCallback
from backend.providers.dto.schema import (
    ChatRequest,
    ChatResponse,
    ChatUsage,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    VideoRequest,
    VideoResponse,
    ImageUnderstandingRequest,
    ImageUnderstandingResponse,
    TextUnderstandingRequest,
    TextUnderstandingResponse,
    VideoUnderstandingRequest,
    VideoUnderstandingResponse, ImageGenerateRequest, ImageGenerateResponse, ImageGenerateChunk
)

load_dotenv()


class VolcanoLLM(LLMBase):
    """火山引擎大模型实现类"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """单例模式实现，确保只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance



    def __init__(self, key: Optional[str] | None, model_name: Optional[str] | None, region: str = "cn-beijing", **kwargs):
        """
        初始化火山引擎大模型客户端
        :param api_key: API密钥 (AK)
        :param model: 默认模型名称，如"doubao-1.5-pro"
        :param region: 区域，默认cn-beijing
        :param kwargs: 其他配置参数：
            - endpoint: API端点，默认open.volcengineapi.com
            - service: 服务名，默认mlp
            - default_embedding_model: 默认嵌入模型，默认bge-large-zh
        """
        # 单例模式：已初始化则直接返回
        if self._initialized:
            return

        key =  os.getenv("DOUBAO_SEED_API_KEY")
        self.default_model = os.getenv("DOUBAO_SEED", "doubao-1.5-pro")
        self.video_model = os.getenv("DOUBAO_SEEDDANCE")
        self.default_embedding_model = os.getenv("EMBED_MODEL")
        # 向量模型可能使用单独的 API Key
        embedding_key = os.getenv("EMBED_API_KEY")

        url ="https://ark.cn-beijing.volces.com/api/v3"

        self.async_client = AsyncArk(
            api_key=key,
            # 豆包API的接入点
            base_url=url
        )

        self.client = Ark(
            api_key=key,
            # 豆包API的接入点
            base_url=url
        )

        # 向量模型客户端（可能使用不同的 API Key）
        self.embedding_client = Ark(
            api_key=embedding_key,
            base_url=url
        )

        # 标记已初始化
        self._initialized = True




    def _chat(self, request: ChatRequest) -> ChatResponse:
        """
        火山引擎对话接口实现
        :param request: 对话请求对象
        :return: 对话响应对象
        :raises BaseAppException: 对话失败、超时或其他错误时抛出异常
        """

        try:
            result = self.client.chat.completions.create(
                messages=[message.model_dump() for message in request.messages],
                model=self.default_model,
                stream=False,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p
            )

            # 处理错误响应
            if hasattr(result, 'error') and result.error:
                error_msg = result.error.get("message", "未知错误") if isinstance(result.error, dict) else str(
                    result.error)
                error_code = result.error.get("code", "") if isinstance(result.error, dict) else ""
                self._handle_error(error_code, error_msg)

            # 构造响应对象
            choice = result.choices[0]
            usage = ChatUsage(
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens
            )

            return ChatResponse(
                content=choice.message.content,
                role=choice.message.role,
                usage=usage,
                model=result.model,
                id=result.id,
                finish_reason=choice.finish_reason
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    def _stream_chat(self, request: ChatRequest) -> Iterator[str]:
        """
        火山引擎流式对话接口实现
        :param request: 对话请求对象
        :return: 流式响应迭代器，返回内容片段
        """

        try:
            response_stream = self.client.chat.completions.create(
                messages=[message.model_dump() for message in request.messages],
                model= self.default_model,
                stream=True,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p
            )

            # 处理流式响应
            for chunk in response_stream:
                if not chunk or not chunk.choices:
                    continue

                choice = chunk.choices[0]
                if choice.delta and choice.delta.content:
                    yield choice.delta.content

                # 如果有结束原因，说明响应结束
                if choice.finish_reason:
                    break

        except ApiException as e:
            self._handle_api_exception(e)



    async def _generate_video(self, request: VideoRequest, prompt: str, image: str | None) -> VideoResponse | None:
        """
        使用Seedance 1.5生成视频

        :param request: 视频生成请求对象
        :param prompt: 视频生成提示词
        :param image: 视频生成首帧（可选）
        :return: 视频生成响应对象
        :raises BaseAppException: 生成失败、超时或其他错误时抛出异常
        """
        try:
            con = [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
            if image:
                con.append(dict(type="image_url", image_url={
                    "url": image  # 首帧图片 URL
                }))

            # 调用视频生成API创建任务
            create_result = await self.async_client.content_generation.tasks.create(
                content=con,
                model= self.video_model,
                generate_audio=request.generate_audio,
                draft=request.draft,
                watermark=request.watermark,
                return_last_frame=request.return_last_frame,
                duration=request.duration,
                ratio=request.ratio,
                resolution=request.resolution,
            )

            task_id = create_result.id
            model_used = request.model or self.video_model

            # 轮询任务状态
            max_retry = 30  # 最多轮询30次，每次间隔10秒，总共5分钟
            retry_count = 0

            while retry_count < max_retry:
                get_result = await self.async_client.content_generation.tasks.get(task_id=task_id)
                status = get_result.status

                if status == "succeeded":
                    # 生成成功，解析结果
                    result_dict = get_result.model_dump() if hasattr(get_result, 'model_dump') else vars(get_result)
                    # 获取实际时长
                    actual_duration = result_dict.get("duration", 0)
                    actual_ratio = result_dict.get("ratio")
                    actual_id = result_dict.get("id", task_id)

                    # 获取视频URL
                    con = result_dict["content"] if hasattr(get_result, 'model_dump') else vars(result_dict)
                    video_url = con["video_url"]

                    if not video_url:
                        raise BaseAppException(AI_GENERATE_FAILED, message="视频生成成功但未获取到视频URL")

                    # 构造响应对象
                    return VideoResponse(
                        video_url=video_url,
                        duration=float(actual_duration) if actual_duration else None,
                        id=actual_id,
                        model=model_used,
                        status=status,
                        resolution=actual_ratio,
                        ratio=actual_ratio
                    )

                elif status == "failed":
                    # 任务失败，获取错误信息
                    result_dict = get_result.model_dump() if hasattr(get_result, 'model_dump') else vars(get_result)
                    error_msg = result_dict.get('error_message') or result_dict.get('error') or "视频生成任务失败"
                    error_code = result_dict.get('error_code', "GENERATE_FAILED")
                    self._handle_error(error_code, error_msg)

                else:
                    # 生成中，等待后继续轮询
                    retry_count += 1
                    await asyncio.sleep(10)

            # 轮询超时
            raise BaseAppException(THIRD_PARTY_TIMEOUT, message=f"视频生成超时，任务ID: {task_id}")

        except ApiException as e:
            self._handle_api_exception(e)
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            # 处理其他异常
            error_msg = getattr(e, 'message', str(e))
            raise BaseAppException(AI_GENERATE_FAILED, message=f"视频生成失败: {error_msg}") from e

    def generate_video_sync(self, request: VideoRequest, prompt: str, image: str | None) -> VideoResponse | None:
        """
        使用Seedance 1.5生成视频（同步版本）

        :param request: 视频生成请求对象
        :param prompt: 视频生成提示词
        :param image: 视频生成首帧（可选）
        :return: 视频生成响应对象
        :raises BaseAppException: 生成失败、超时或其他错误时抛出异常
        """
        import time

        try:
            con = [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
            if image:
                con.append(dict(type="image_url", image_url={
                    "url": image  # 首帧图片 URL
                }))

            # 调用视频生成API创建任务（使用同步客户端）
            create_result = self.client.content_generation.tasks.create(
                content=con,
                model=self.video_model,
                generate_audio=request.generate_audio,
                draft=request.draft,
                watermark=request.watermark,
                return_last_frame=request.return_last_frame,
                duration=request.duration,
                ratio=request.ratio,
                resolution=request.resolution,
            )

            task_id = create_result.id
            model_used = request.model or self.video_model

            # 轮询任务状态
            max_retry = 30  # 最多轮询30次，每次间隔10秒，总共5分钟
            retry_count = 0

            while retry_count < max_retry:
                get_result = self.client.content_generation.tasks.get(task_id=task_id)
                status = get_result.status

                if status == "succeeded":
                    # 生成成功，解析结果
                    result_dict = get_result.model_dump() if hasattr(get_result, 'model_dump') else vars(get_result)
                    # 获取实际时长
                    actual_duration = result_dict.get("duration", 0)
                    actual_ratio = result_dict.get("ratio")
                    actual_id = result_dict.get("id", task_id)

                    # 获取视频URL
                    con = result_dict["content"] if hasattr(get_result, 'model_dump') else vars(result_dict)
                    video_url = con["video_url"]

                    if not video_url:
                        raise BaseAppException(AI_GENERATE_FAILED, message="视频生成成功但未获取到视频URL")

                    # 构造响应对象
                    return VideoResponse(
                        video_url=video_url,
                        duration=float(actual_duration) if actual_duration else None,
                        id=actual_id,
                        model=model_used,
                        status=status,
                        resolution=actual_ratio,
                        ratio=actual_ratio
                    )

                elif status == "failed":
                    # 任务失败，获取错误信息
                    result_dict = get_result.model_dump() if hasattr(get_result, 'model_dump') else vars(get_result)
                    error_msg = result_dict.get('error_message') or result_dict.get('error') or "视频生成任务失败"
                    error_code = result_dict.get('error_code', "GENERATE_FAILED")
                    self._handle_error(error_code, error_msg)

                else:
                    # 生成中，等待后继续轮询
                    retry_count += 1
                    time.sleep(10)

            # 轮询超时
            raise BaseAppException(THIRD_PARTY_TIMEOUT, message=f"视频生成超时，任务ID: {task_id}")

        except ApiException as e:
            self._handle_api_exception(e)
        except Exception as e:
            if isinstance(e, BaseAppException):
                raise e
            # 处理其他异常
            error_msg = getattr(e, 'message', str(e))
            raise BaseAppException(AI_GENERATE_FAILED, message=f"视频生成失败: {error_msg}") from e

    def _embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        多模态嵌入接口实现
        :param request: 嵌入请求对象
        :return: 嵌入响应对象
        """
        try:
            # 调用嵌入API（使用单独的向量模型客户端）
            # 多模态嵌入接口要求 input 为 [{type, text}] 格式
            input_content = [text.model_dump() for text in request.texts]
            response = self.embedding_client.multimodal_embeddings.create(
                input=input_content,
                model=self.default_embedding_model
            )

            # 提取嵌入向量（response.data 可能是单个对象或列表）
            if isinstance(response.data, list):
                embeddings = [item.embedding for item in response.data]
            else:
                embeddings = [response.data.embedding]

            # 构造使用情况（response.usage 可能是 dict 或对象）
            usage_data = response.usage
            if isinstance(usage_data, dict):
                usage = EmbeddingUsage(
                    prompt_tokens=usage_data.get('prompt_tokens', 0),
                    total_tokens=usage_data.get('total_tokens', 0)
                )
            else:
                usage = EmbeddingUsage(
                    prompt_tokens=usage_data.prompt_tokens,
                    total_tokens=usage_data.total_tokens
                )

            return EmbeddingResponse(
                embeddings=embeddings,
                usage=usage,
                model=response.model
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    def _image_understanding(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口(chat)
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        try:
            # 构造多模态消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {"type": "image_url", "image_url": {"url": request.image_url}}
                    ]
                }
            ]

            # 调用多模态对话API
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.default_model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stream=False
            )

            # 构造响应
            choice = response.choices[0]
            usage = ChatUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )

            return ImageUnderstandingResponse(
                content=choice.message.content,
                usage=usage,
                model=response.model,
                id=response.id
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None


    async def _image_understanding_response(self, request: ImageUnderstandingRequest) -> ImageUnderstandingResponse:
        """
        图片理解接口(chat)
        :param request: 图片理解请求对象
        :return: 图片理解响应对象
        """
        try:
            # 构造多模态消息
            meg=[
            {"role": "user", "content": [
                {
                    "type": "input_image",
                    "image_url": f"file://{request.image_url}"
                },
                {
                    "type": "input_text",
                    "text": request.prompt
                }
            ]},
        ]
            # 调用多模态对话API
            response = await self.async_client.responses.create(
                model=self.default_model,
                input=meg,
                temperature=request.temperature,
                top_p=request.top_p,
                stream=False
            )

            # 处理错误响应
            if hasattr(response, 'error') and response.error:
                error_msg = response.error.get("message", "未知错误") if isinstance(response.error, dict) else str(
                    response.error)
                error_code = response.error.get("code", "") if isinstance(response.error, dict) else ""
                self._handle_error(error_code, error_msg)

            # 查找message类型的输出项
            message = None
            for item in response.output:
                if item.type == 'message':
                    message = item
                    break

            if not message:
                raise BaseAppException(AI_GENERATE_FAILED, message="响应中未找到消息内容")

            # 提取文本内容
            content = ""
            for content_item in message.content:
                if content_item.type == 'output_text':
                    content = content_item.text
                    break

            # 构造使用情况
            usage = ChatUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens
            )

            return ImageUnderstandingResponse(
                content=content,
                usage=usage,
                model=response.model,
                id=response.id
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    def _text_understanding(self, request: TextUnderstandingRequest) -> TextUnderstandingResponse:
        """
        文本理解接口
        :param request: 文本理解请求对象
        :return: 文本理解响应对象
        """
        try:
            # 构造消息
            messages = [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": request.text}
            ]

            # 调用对话API
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.default_model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stream=False
            )

            # 构造响应
            choice = response.choices[0]
            usage = ChatUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )

            return TextUnderstandingResponse(
                content=choice.message.content,
                usage=usage,
                model=response.model,
                id=response.id
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    async def _video_understanding_response(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口(responses)
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        :raises BaseAppException: 理解失败、超时或其他错误时抛出异常
        """
        try:
            # 构造多模态消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "input_text": request.prompt},
                        {"type": "input_video", "video_url": request.video_url}
                    ]
                }
            ]

            # 调用多模态对话API
            response = await self.async_client.responses.create(
                model=self.default_model,
                input=messages,
                temperature=request.temperature,
                top_p=request.top_p,
                stream=False
            )

            # 处理错误响应
            if hasattr(response, 'error') and response.error:
                error_msg = response.error.get("message", "未知错误") if isinstance(response.error, dict) else str(
                    response.error)
                error_code = response.error.get("code", "") if isinstance(response.error, dict) else ""
                self._handle_error(error_code, error_msg)

            # 查找message类型的输出项
            message = None
            for item in response.output:
                if item.type == 'message':
                    message = item
                    break

            if not message:
                raise BaseAppException(AI_GENERATE_FAILED, message="响应中未找到消息内容")

            # 提取文本内容
            content = ""
            for content_item in message.content:
                if content_item.type == 'output_text':
                    content = content_item.text
                    break

            # 构造使用情况
            usage = ChatUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens
            )

            return VideoUnderstandingResponse(
                content=content,
                usage=usage,
                model=response.model,
                id=response.id
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    async def _video_understanding(self, request: VideoUnderstandingRequest) -> VideoUnderstandingResponse:
        """
        视频理解接口（异步）
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        :raises BaseAppException: 理解失败、超时或其他错误时抛出异常
        """
        try:
            # 构造多模态消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {"type": "video_url", "video_url": {"url": request.video_url}}
                    ]
                }
            ]

            # 调用异步多模态对话API
            response = await self.async_client.chat.completions.create(
                messages=messages,
                model=self.default_model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stream=False
            )

            # 构造响应
            choice = response.choices[0]
            usage = ChatUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )

            return VideoUnderstandingResponse(
                content=choice.message.content,
                usage=usage,
                model=response.model,
                id=response.id
            )

        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    async def _video_understanding_response_file(self, request: VideoUnderstandingRequest) -> None:
        """
        视频理解接口（异步）
        :param request: 视频理解请求对象
        :return: 视频理解响应对象
        :raises BaseAppException: 理解失败、超时或其他错误时抛出异常
        """
        try:

            # 构造多模态消息
            config = {
                    "video": {
                        "fps": 0.3,  # define the sampling fps of the video, default is 1.0
                    }
                }

            file = await self.async_client.files.create(
                file=open(request.video_url, "rb"),
                purpose="user_data",
                preprocess_configs=config
            )

            await self.async_client.files.wait_for_processing(file.id)

            msg = [
                    {"role": "user", "content": [
                        {
                            "type": "input_video",
                            "file_id": file.id  # ref video file id
                        },
                        {
                            "type": "input_text",
                            "text": request.prompt

                        }
                    ]},
                ]

            response = await self.async_client.responses.create(
                model="doubao-seed-2-0-lite-260215",
                input=msg,
            )


        except ApiException as e:
            self._handle_api_exception(e)
            raise  # 确保方法总是抛出异常，不会返回None

    def _image_create_stream(self,request: ImageGenerateRequest, callback: ImageCallback):

        stream = self.embedding_client.images.generate(
            # Replace with Model ID
            model="doubao-seedream-4-5-251128",
            prompt=request.prompt,
            image=request.image,
            size=request.size,
            sequential_image_generation=request.sequential_image_generation,
            sequential_image_generation_options=SequentialImageGenerationOptions(max_images=request.max_images),
            output_format=request.output_format,
            response_format=request.response_format,
            stream=request.stream,
            watermark=request.watermark
        )

        image_urls = []
        total_usage = None
        for event in stream:
            if event is None:
                continue
            if event.type == "image_generation.partial_failed":
                callback.on_error(Exception(event.error.message if hasattr(event, 'error') and event.error else "图片生成失败"))
            elif event.type == "image_generation.partial_succeeded":
                if event.error is None and event.url:
                    # 获取图片索引，如果不存在则使用当前列表长度作为索引
                    partial_image_index = getattr(event, 'partial_image_index', len(image_urls))
                    chunk = ImageGenerateChunk(
                        url=event.url,
                        partial_image_index=partial_image_index)
                    image_urls.append(chunk)
                    callback.on_next(chunk)
            elif event.type == "image_generation.completed":
                # 构造usage信息，如果响应中包含的话
                usage = None
                if hasattr(event, 'usage') and event.usage:
                    usage_data = event.usage
                    if isinstance(usage_data, dict):
                        usage = ChatUsage(
                            prompt_tokens=usage_data.get('prompt_tokens', 0),
                            completion_tokens=usage_data.get('completion_tokens', 0),
                            total_tokens=usage_data.get('total_tokens', 0)
                        )
                    else:
                        usage = ChatUsage(
                            prompt_tokens=getattr(usage_data, 'prompt_tokens', 0),
                            completion_tokens=getattr(usage_data, 'completion_tokens', 0),
                            total_tokens=getattr(usage_data, 'total_tokens', 0)
                        )

                callback.on_complete(ImageGenerateResponse(
                    urls=image_urls,
                    usage=usage
                ))

    def _image_create(self, request: ImageGenerateRequest):

        response = self.embedding_client.images.generate(
            # Replace with Model ID
            model="doubao-seedream-4-5-251128",
            prompt=request.prompt,
            image=request.image,
            size=request.size,
            response_format=request.response_format,
            stream=False,
            watermark=request.watermark
        )
        chunks = []
        for image in response.data:
            chunks.append(ImageGenerateChunk(
                url=image.url
            ))

        # 构造usage信息，如果响应中包含的话
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage_data = response.usage
            if isinstance(usage_data, dict):
                usage = ChatUsage(
                    prompt_tokens=usage_data.get('prompt_tokens', 0),
                    completion_tokens=usage_data.get('completion_tokens', 0),
                    total_tokens=usage_data.get('total_tokens', 0)
                )
            else:
                usage = ChatUsage(
                    prompt_tokens=getattr(usage_data, 'prompt_tokens', 0),
                    completion_tokens=getattr(usage_data, 'completion_tokens', 0),
                    total_tokens=getattr(usage_data, 'total_tokens', 0)
                )

        return ImageGenerateResponse(
            urls=chunks,
            usage=usage
        )









    def _handle_api_exception(self, e: ApiException):
        """
        处理API调用异常
        :param e: ApiException
        """
        if e.status == 408 or "timeout" in str(e).lower():
            raise BaseAppException(THIRD_PARTY_TIMEOUT, message=f"火山引擎服务调用超时: {str(e)}") from e
        elif e.status >= 500:
            raise BaseAppException(AI_SERVICE_ERROR, message=f"火山引擎服务内部错误: {str(e)}") from e
        else:
            raise BaseAppException(AI_SERVICE_ERROR, message=f"火山引擎服务调用失败: {str(e)} (状态码: {e.status})") from e

    def _handle_error(self,error_code: str, error_msg: str):
        """
        处理火山引擎API返回的错误
        :param error_code: 错误码
        :param error_msg: 错误信息
        """
        # 根据错误码映射到自定义异常
        if "quota" in error_code.lower() or "exhausted" in error_msg.lower():
            raise BaseAppException(AI_QUOTA_EXHAUSTED, message=error_msg)
        elif "content" in error_code.lower() or "violation" in error_msg.lower() or "审核" in error_msg:
            raise BaseAppException(AI_CONTENT_VIOLATION, message=error_msg)
        elif "timeout" in error_code.lower():
            raise BaseAppException(THIRD_PARTY_TIMEOUT, message=f"火山引擎服务超时: {error_msg}")
        else:
            raise BaseAppException(AI_GENERATE_FAILED, message=f"生成失败: {error_msg} (错误码: {error_code})")




