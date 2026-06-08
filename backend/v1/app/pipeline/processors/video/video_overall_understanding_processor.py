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
        - aggregated_video_data: Dict 聚合后的视频完整数据（VideoAggregationProcessor输出，包含完整的slices_detail）
        - all_script_lines: List[str] 所有分片的台词列表（VideoAggregationProcessor输出）
        - video_id: str 视频ID（初始输入）
        - video_duration: int 视频总时长（毫秒，初始输入）

        输出（写入上下文）：
        - ai_features: Dict 视频整体理解结构化结果
        - embed_video: str 扁平化后的视频整体数据，用于向量化
        """
        aggregated_data = context.get(constants.AGGREGATED_VIDEO_DATA, {})
        all_script_lines = context.get(constants.ALL_SCRIPT_LINES, [])
        video_id = context.get(constants.VIDEO_ID)
        video_duration = context.get("video_duration", 0)

        if not aggregated_data:
            raise ValueError("No aggregated video data found in context, please ensure VideoAggregationProcessor executed successfully")

        # 构建结构化的分片信息文本
        segment_info_lines = []

        # 使用聚合数据中的完整分片详情，而不是截断的segment_list
        slices_detail = aggregated_data.get("slices_detail", [])

        if len(slices_detail) == 0:
            raise BusinessException("No slices detail found in aggregated data, please ensure VideoAggregationProcessor executed successfully")

        for i, slice_info in enumerate(slices_detail):
            understanding = slice_info.get("understanding", {})
            creative_elements = understanding.get(prompt_manager.FIELD_CREATIVE_ELEMENTS, {})
            full_content = understanding.get(prompt_manager.FIELD_GENERATE_PROMPT, "")

            segment_info_lines.append(
                f"分片{i+1}(ID:{slice_info['slice_id']}): 模板类型={understanding.get(prompt_manager.FIELD_TEMPLATE_TYPE, '')}, 模板名称={understanding.get(prompt_manager.FIELD_TEMPLATE_NAME, '')}, 完整内容={full_content}"
            )
        segment_info_str = "\n".join(segment_info_lines)

        # 构建完整的输入文本
        full_input = f"""
视频ID: {video_id}
视频总时长: {video_duration}ms
总分片数: {len(slices_detail)}

所有台词:
{chr(10).join(all_script_lines)}

分片详情:
{segment_info_str}
"""

        # 使用预定义的视频整体理解提示词（已包含完整的输出结构要求）
        prompt = self.prompt_template


        # 构建大模型请求
        request = TextUnderstandingRequest(
            prompt=prompt,
            text=full_input,
            max_tokens=16384,  # 整体理解内容较多，设置更大的token限制
            temperature=0.1,  # 整体理解需要更稳定的输出
            top_p=0.9
        )

        # 尝试异步调用（如果方法是异步的）
        if inspect.iscoroutinefunction(self.llm_client.text_understanding):
            coro = self.llm_client.text_understanding(request)
            # 使用辅助方法运行异步函数，处理已有事件循环的情况
            response = self._run_async(coro)
        else:
            # 同步调用
            response = self.llm_client.text_understanding(request)

        # 解析返回结果
        try:
            # 先清理响应内容，移除可能的markdown标记和多余文本
            content = response.content.strip()
            # 移除可能的```json和```包裹
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            # 寻找JSON边界
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx >= 0 and end_idx >= 0 and end_idx > start_idx:
                content = content[start_idx:end_idx+1]

            resolve = json.loads(content)
        except json.JSONDecodeError as e:
            # 记录原始响应内容方便调试
            logger.error(f"Video overall JSON parse failed. Raw content: {response.content[:1000]}...")
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
