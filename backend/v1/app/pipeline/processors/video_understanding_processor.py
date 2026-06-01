import asyncio
import json
from typing import Dict, List

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import VideoUnderstandingRequest
from backend.v1.app.pipeline.utils import load_template, load_prompt
from backend.v1.app.pipeline.utils.json_flattener import JsonFlattener


class VideoUnderstandingProcessor(BaseProcessor):
    """
    视频理解处理器
    调用大模型接口分析每个视频片段的内容
    """

    def __init__(self, llm_client=None):
        """
        初始化视频理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        prompt_config = load_prompt("slice_understanding")
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
        执行视频理解逻辑

        输入（从上下文获取）：
        - slices_url: List[str] 视频分片URL列表（VideoSplitProcessor输出）
        - images_url: List[str] 视频分片封面图URL列表（VideoSplitProcessor输出）
        - slices_object_name: List[str] 视频分片对象存储名称列表（VideoSplitProcessor输出）
        - images_object_name: List[str] 视频分片封面图对象存储名称列表（VideoSplitProcessor输出）
        - count: int 分片总数量（VideoSplitProcessor输出）
        - video_id: str 视频ID（初始输入）

        输出（写入上下文）：
        - understood_slices: List[Dict] 理解后的分片结构化数据，包含所有基础信息和理解结果
        - embed_slices: List[Dict] 扁平化后的分片数据，用于向量化

        :param context: 流水线上下文
        :return: 修改后的上下文，包含大模型理解结果
        """
        # 从上下文获取分片数据
        slices_url = context.get("slices_url", [])
        images_url = context.get("images_url", [])
        slices_object_name = context.get("slices_object_name", [])
        images_object_name = context.get("images_object_name", [])
        slice_count = context.get("count", 0)
        video_id = context.get("video_id")

        if not slices_url or slice_count == 0:
            raise ValueError("No slices found in context, please ensure VideoSplitProcessor executed successfully")
        if len(slices_url) != slice_count:
            raise ValueError(f"Slice count mismatch: count={slice_count}, slices_url length={len(slices_url)}")

        # 加载分片理解Prompt模板
        prompt_template = self.prompt_template.format(json_info=json.dumps(load_template("slice"), ensure_ascii=False))

        understood_slices = []
        embed_slices = []

        for i in range(slice_count):
            # 构建大模型请求
            try:
                # 尝试异步调用（如果方法是异步的）
                import inspect
                if inspect.iscoroutinefunction(self.llm_client.video_understanding):
                    coro = self.llm_client.video_understanding(VideoUnderstandingRequest(
                        video_url=slices_url[i],
                        prompt=prompt_template,
                        max_tokens=2048,
                        temperature=0.7,
                        top_p=0.9
                    ))
                    # 使用辅助方法运行异步函数，处理已有事件循环的情况
                    response = self._run_async(coro)
                else:
                    # 同步调用
                    response = self.llm_client.video_understanding(VideoUnderstandingRequest(
                        video_url=slices_url[i],
                        prompt=prompt_template,
                        max_tokens=2048,
                        temperature=0.7,
                        top_p=0.9
                    ))
            except Exception as e:
                context.add_error(ValueError(f"Slice {i} understanding failed: {str(e)}"))
                continue

            # 解析大模型返回的JSON结果
            try:
                understanding_result = json.loads(response.content)
            except json.JSONDecodeError as e:
                context.add_error(ValueError(f"Slice {i} understanding result parse failed: {str(e)}"))
                continue

            # 构建完整的分片数据，合并基础信息和理解结果
            slice_data = {
                "slice_id": f"{video_id}_slice_{i}",
                "video_id": video_id,
                "slice_index": i,
                "slice_url": slices_url[i],
                "cover_url": images_url[i] if i < len(images_url) else "",
                "slice_object_name": slices_object_name[i],
                "cover_object_name": images_object_name[i] if i < len(images_object_name) else "",
                "understanding": understanding_result
            }

            understood_slices.append(slice_data)
            # 准备向量化数据：包含原始内容和元数据
            # 先添加slice_id和video_id到理解结果中，再扁平化
            understanding_with_id = understanding_result.copy()
            understanding_with_id["slice_id"] = slice_data["slice_id"]
            understanding_with_id["video_id"] = video_id
            flattened = JsonFlattener.flatten(understanding_with_id)

            # VectorizationProcessor需要dict格式，包含content和元数据字段
            embed_data = {
                "slice_id": slice_data["slice_id"],
                "content": flattened,
                "start_time": slice_data.get("start_time", 0.0),
                "end_time": slice_data.get("end_time", 0.0)
            }
            embed_slices.append(embed_data)

        # 存储结果到上下文
        context.set("understood_slices", understood_slices)
        context.set("embed_slices", embed_slices)
        # 将视频封面图列表存入上下文，供后续图像向量化使用
        context.set("slice_cover_urls", images_url)

        return context
