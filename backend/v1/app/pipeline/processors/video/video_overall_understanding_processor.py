import json
import os
import asyncio
import inspect
from typing import Dict, List

from backend.framework.exceptions import BusinessException
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, TextContent, TextUnderstandingRequest
from backend.v1.app.pipeline.utils import prompt_manager, JsonFlattener


class VideoOverallUnderstandingProcessor(BaseProcessor):
    """
    视频整体理解处理器
    基于聚合后的分片结果，对整个视频进行整体分析
    """

    def __init__(self, llm_client=None):
        """
        初始化视频整体理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)
        self.prompt_template = prompt_manager.get_video_overall_understanding_prompt()

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
        执行视频整体理解逻辑

        输入（从上下文获取）：
        - aggregated_video_data: Dict 聚合后的视频完整数据（VideoAggregationProcessor输出）
        - segment_list: List[Dict] 分片索引列表（VideoAggregationProcessor输出）
        - all_script_lines: List[str] 所有分片的台词列表（VideoAggregationProcessor输出）
        - video_id: str 视频ID（初始输入）
        - video_duration: int 视频总时长（毫秒，初始输入）

        输出（写入上下文）：
        - ai_features: Dict 视频整体理解结构化结果
        - embed_video: str 扁平化后的视频整体数据，用于向量化
        """
        aggregated_data = context.get(constants.AGGREGATED_VIDEO_DATA, {})
        segment_list = context.get(constants.SEGMENT_LIST, [])
        all_script_lines = context.get(constants.ALL_SCRIPT_LINES, [])
        video_id = context.get(constants.VIDEO_ID)
        video_duration = context.get("video_duration", 0)

        if not aggregated_data or not segment_list:
            raise ValueError("No aggregated video data found in context, please ensure VideoAggregationProcessor executed successfully")

        # 构建结构化的分片信息文本
        segment_info_lines = []

        if len(segment_list) == 0:
            raise BusinessException("No segments found in context, please ensure VideoAggregationProcessor executed successfully")


        for i, segment in enumerate(segment_list):
            segment_info_lines.append(
                f"分片{i+1}(ID:{segment['slice_id']}): 模板类型={segment['template_type']}, 模板名称={segment['template_name']}, 内容摘要={segment['content_summary']}"
            )
        segment_info_str = "\n".join(segment_info_lines)

        # 构建完整的输入文本
        full_input = f"""
视频ID: {video_id}
视频总时长: {video_duration}ms
总分片数: {len(segment_list)}

所有台词:
{chr(10).join(all_script_lines)}

分片详情:
{segment_info_str}
"""

        # 使用预定义的视频整体理解提示词（已包含完整的输出结构要求）
        prompt = self.prompt_template


        # 构建大模型请求
        response = self.llm_client.text_understanding(TextUnderstandingRequest(
            prompt=prompt,
            text=full_input
        ))

        # 解析返回结果
        try:
            resolve = json.loads(response.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Video overall understanding result parse failed: {str(e)}")

        # 补充视频基础信息
        if "视频基本信息" in resolve:
            resolve["视频基本信息"]["video_id"] = video_id
            resolve["视频基本信息"]["总时长_ms"] = video_duration
            resolve["视频基本信息"]["原片核心文案"] = all_script_lines

        # 扁平化结果用于向量化
        # 先添加video_id到结果中，再扁平化
        resolve_with_id = resolve.copy()
        resolve_with_id["video_id"] = video_id
        flattened = JsonFlattener.flatten(resolve_with_id)

        # VectorizationProcessor需要dict格式，包含content和元数据字段
        embed_video = {
            "video_id": video_id,
            "content": flattened,
            "title": resolve.get("视频基本信息", {}).get("商品名称", ""),
            "category": "general",
            "tags": []
        }

        # 存储到上下文
        context.set(constants.AI_FEATURES, resolve)
        context.set(constants.EMBED_VIDEO, embed_video)

        return context
