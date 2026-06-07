from typing import Dict, List, Union
import asyncio
import inspect
import json
import logging

from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.pipeline.utils import prompt_manager
from backend.providers import VolcanoLLM, ImageUnderstandingRequest

logger = logging.getLogger(__name__)
from backend.providers.dto.schema import (
    ChatRequest,
    ChatMessage,
    TextContent,
    ImageUrlContent,
    MultimodalContent
)


class ProductUnderstandingProcessor(BaseProcessor):
    """
    商品理解处理器
    接收图文混合内容，调用大模型分析商品信息
    """

    def __init__(self, llm_client=None):
        """
        初始化商品理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        # 使用prompt_manager获取包含完整schema的提示词
        self.prompt_template = prompt_manager.get_product_understanding_prompt()

    def _run_async(self, coro):
        """
        从同步上下文中运行异步函数，处理已有事件循环的情况
        :param coro: 要运行的协程
        :return: 协程的返回值
        """
        try:
            # 检查是否有正在运行的事件循环
            loop = asyncio.get_running_loop()
            # 如果有运行中的循环，在新线程中运行异步函数避免死锁
            import threading
            result = None
            def run_in_thread():
                nonlocal result
                # 新线程中创建新的事件循环
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            return result
        except RuntimeError:
            # 没有运行中的循环，直接使用asyncio.run
            return asyncio.run(coro)

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行商品理解逻辑

        :param context: 流水线上下文，需要包含 multimodal_content 字段
        :return: 修改后的上下文，包含商品理解结果
        """
        images = context.get("images")
        description = context.get("description", "")

        if not description and not images:
            raise ValueError("multimodal_content is required in context")

        # 处理图片列表
        image_url = None
        if images:
            if isinstance(images, list):
                if len(images) > 1:
                    logger.warning(f"检测到{len(images)}张图片，当前版本仅支持处理第一张图片，其余图片将被忽略")
                image_url = images[0]
            else:
                image_url = images

        # 构建大模型请求，将提示词模板与用户描述结合
        prompt = f"{self.prompt_template}\n\n商品描述：{description}" if description else self.prompt_template
        request = ImageUnderstandingRequest(
            prompt=prompt,
            image_url=image_url,
            max_tokens=8192,  # 增大token限制，容纳完整的商品信息结构
            temperature=0.1,  # 降低温度，确保输出格式稳定
            top_p=0.9,
            model="_llama2_7b_chat_v2",
        )

        # 尝试异步调用（如果方法是异步的）
        if inspect.iscoroutinefunction(self.llm_client.image_understanding):
            coro = self.llm_client.image_understanding(request)
            # 使用辅助方法运行异步函数，处理已有事件循环的情况
            response = self._run_async(coro)
        else:
            # 同步调用
            response = self.llm_client.image_understanding(request)

        try:
            understanding_result = json.loads(response.content)
        except json.JSONDecodeError:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx >= 0 and end_idx > start_idx:
                content = content[start_idx:end_idx + 1]
            understanding_result = json.loads(content)

        context.set("product_understanding", understanding_result)


        return context
