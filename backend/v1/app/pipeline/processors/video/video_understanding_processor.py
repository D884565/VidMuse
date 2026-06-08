import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from fsspec.asyn import loop

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.providers import VolcanoLLM, VideoUnderstandingResponse
from backend.providers.dto.schema import VideoUnderstandingRequest
from backend.v1.app.pipeline.utils import prompt_manager, JsonFlattener


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
        self.prompt_template = prompt_manager.get_slice_understanding_prompt()

    def run_async(self ,coro):
        """万能异步运行器，兼容所有环境"""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # 已有循环在跑，用线程池避免冲突
                with ThreadPoolExecutor(max_workers=1) as executor:
                    return executor.submit(
                        lambda: asyncio.run(coro)
                    ).result()
        except RuntimeError:
            pass

        # 没有运行中的循环，直接 run
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
        slices_url = context.get(constants.SLICES_URL, [])
        slices_object_name = context.get(constants.SLICES_OBJECT_NAME, [])
        slice_count = context.get(constants.SLICE_COUNT, 0)
        video_id = context.get(constants.VIDEO_ID)
        # 首帧提取已禁用，相关字段保留为空以保持兼容性
        images_url = []
        images_object_name = []

        if not slices_url or slice_count == 0:
            raise ValueError("No slices found in context, please ensure VideoSplitProcessor executed successfully")
        if len(slices_url) != slice_count:
            raise ValueError(f"Slice count mismatch: count={slice_count}, slices_url length={len(slices_url)}")

        # 使用预定义的分片理解提示词（已包含完整的输出结构要求）
        prompt_template = self.prompt_template

        understood_slices = []
        embed_slices = []
        failed_slices = []  # 记录失败的分片索引

        for i in range(slice_count):
            # 构建大模型请求
            try:
                # 尝试异步调用（如果方法是异步的） # 同步调用
                response = self.run_async(self.llm_client.video_understanding(VideoUnderstandingRequest(
                    video_url=slices_url[i],
                    prompt=prompt_template,
                    max_tokens=8192,  # 增大token限制，避免JSON被截断
                    temperature=0.7,
                    top_p=0.9
                )))
            except Exception as e:
                error_msg = f"Slice {i} understanding failed: {str(e)}"
                context.add_error(ValueError(error_msg))
                failed_slices.append(i)
                logger.error(error_msg)
                continue

            # 解析大模型返回的JSON结果
            try :
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

                understanding_result = json.loads(content)
            except json.JSONDecodeError as e:
                # 记录原始响应内容方便调试
                error_msg = f"Slice {i} JSON parse failed. Raw content: {response.content[:1000]}..."
                logger.error(error_msg)
                context.add_error(ValueError(f"Slice {i} understanding result parse failed: {str(e)}"))
                failed_slices.append(i)
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

            # 从理解结果中获取时间信息，或通过切片索引计算（每个切片默认10秒）
            understanding = slice_data.get("understanding", {})
            start_time = understanding.get(prompt_manager.FIELD_CREATIVE_ELEMENTS, {}).get("start_time", i * 10.0)
            end_time = understanding.get(prompt_manager.FIELD_CREATIVE_ELEMENTS, {}).get("end_time", (i + 1) * 10.0)

            # VectorizationProcessor需要dict格式，包含content和元数据字段
            embed_data = {
                "slice_id": slice_data["slice_id"],
                "content": flattened,
                "start_time": float(start_time),
                "end_time": float(end_time)
            }
            embed_slices.append(embed_data)

        # 存储结果到上下文
        context.set(constants.UNDERSTOOD_SLICES, understood_slices)
        context.set(constants.EMBED_SLICES, embed_slices)
        # 首帧提取已禁用，图像向量化已关闭，此字段保留为空以保持兼容性
        context.set(constants.SLICE_COVER_URLS, images_url)

        # 汇总分片处理结果
        total_slices = slice_count
        success_count = len(understood_slices)
        failed_count = len(failed_slices)

        # 记录分片处理统计信息
        context.metadata["slice_processing_stats"] = {
            "total_slices": total_slices,
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_slices": failed_slices
        }

        # 如果有失败的分片，添加汇总错误信息
        if failed_count > 0:
            summary_error = f"分片处理完成，共{total_slices}个分片，成功{success_count}个，失败{failed_count}个，失败分片索引: {failed_slices}"
            logger.warning(summary_error)
            # 仅在完全没有成功分片时才添加致命错误，否则仅记录警告
            if success_count == 0:
                context.add_error(ValueError(f"所有分片处理失败: {summary_error}"))
            else:
                logger.info(f"部分分片处理失败，但仍有{success_count}个分片成功，继续后续处理")

        return context
