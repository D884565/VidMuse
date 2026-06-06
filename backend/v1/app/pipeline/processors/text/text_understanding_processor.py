from typing import Dict, List, Union
import asyncio
import inspect
import json
import logging

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.pipeline.utils import load_prompt
from backend.providers import VolcanoLLM, TextUnderstandingRequest
from backend.providers.dto.schema import TextContent

logger = logging.getLogger(__name__)


class TextUnderstandingProcessor(BaseProcessor):
    """
    文本理解处理器
    接收商品描述文本，调用大模型分析商品信息
    输出格式与ProductUnderstandingProcessor保持一致，方便后续统一处理
    """

    def __init__(self, llm_client=None):
        """
        初始化文本理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM()
        prompt_config = load_prompt("product_understanding")  # 复用商品理解的提示词模板
        self.prompt_template = prompt_config["template"]

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

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行文本理解逻辑

        :param context: 流水线上下文，需要包含 description 字段
        :return: 修改后的上下文，包含商品理解结果（与图片理解格式一致）
        """
        description = context.get("description", "")
        product_id = context.get("product_id", "")

        if not description:
            raise ValueError("description is required for text understanding")

        # 构建大模型请求
        prompt = f"{self.prompt_template}\n\n商品描述：{description}"

        request = TextUnderstandingRequest(
            prompt=prompt,
            text=description,
            max_tokens=8192,
            temperature=0.1,
            top_p=0.9
        )

        # 调用大模型接口
        try:
            if inspect.iscoroutinefunction(self.llm_client.text_understanding):
                coro = self.llm_client.text_understanding(request)
                response = self._run_async(coro)
            else:
                response = self.llm_client.text_understanding(request)

            # 解析返回结果，保持与图片理解相同的格式
            try:
                understanding_result = json.loads(response.content)
            except json.JSONDecodeError as e:
                # 清理JSON格式
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx >= 0 and end_idx > start_idx:
                    content = content[start_idx:end_idx + 1]
                understanding_result = json.loads(content)

            # 存储结果，格式与图片理解完全一致
            context.set("product_understanding", understanding_result)
            logger.info(f"文本理解完成，product_id: {product_id}")

        except Exception as e:
            logger.error(f"文本理解失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"文本理解失败: {str(e)}"))

        return context
