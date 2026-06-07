import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import VideoUnderstandingRequest
from backend.v1.app.pipeline.utils import prompt_manager, JsonFlattener
import logging

logger = logging.getLogger(__name__)


class DirectVideoUnderstandingProcessor(BaseProcessor):
    """
    直接视频理解处理器
    接收完整视频URL，调用大模型一次性输出符合格式要求的video.json和slice.json结构
    """

    def __init__(self, llm_client=None):
        """
        初始化直接视频理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)

    def run_async(self, coro):
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
        - video_url: str 完整视频URL（必填）
        - video_id: str 视频ID（必填）
        - asset_id: int 资产ID（必填）
        - video_duration: int 视频总时长（可选，毫秒）

        输出（写入上下文）：
        - slice_data: List[Dict] 符合现有格式的分片结构化数据
        - video_data: Dict 符合现有格式的整体视频结构化数据
        - embed_slices: List[Dict] 扁平化后的分片数据，用于向量化
        - embed_video: Dict 扁平化后的整体视频数据，用于向量化
        - ai_features: Dict 最终要落库的结构化数据

        :param context: 流水线上下文
        :return: 修改后的上下文，包含大模型理解结果
        """
        # 从上下文获取必要参数
        # 兼容多种键名：优先使用video_url，其次是video_file，最后是constants.VIDEO_URL
        video_url = context.get("video_url") or context.get("video_file") or context.get(constants.VIDEO_URL)
        video_id = context.get(constants.VIDEO_ID)
        asset_id = context.get("asset_id")
        video_duration = context.get("video_duration", 0)

        if not video_url:
            raise ValueError("video_url is required for direct video understanding")
        if not video_id:
            raise ValueError("video_id is required for direct video understanding")
        if not asset_id:
            raise ValueError("asset_id is required for direct video understanding")

        # 构建大模型请求
        try:
            # 获取格式化好的提示词，包含完整schema和动态参数
            formatted_prompt = prompt_manager.get_direct_video_understanding_prompt(
                video_url=video_url,
                video_duration=video_duration
            )
            response = self.run_async(self.llm_client.video_understanding(VideoUnderstandingRequest(
                video_url=video_url,
                prompt=formatted_prompt,
                max_tokens=32768,  # 增大token限制，避免复杂JSON被截断
                temperature=0.1,  # 降低温度，确保输出格式稳定
                top_p=0.9
            )))
        except Exception as e:
            error_msg = f"Direct video understanding failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            context.add_error(ValueError(error_msg))
            return context

        # 解析大模型返回的JSON结果
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

            result = json.loads(content)
        except json.JSONDecodeError as e:
            # 记录原始响应内容方便调试
            error_msg = f"Direct video understanding JSON parse failed. Raw content: {response.content[:2000]}..."
            logger.error(error_msg)
            context.add_error(ValueError(f"Direct video understanding result parse failed: {str(e)}"))
            return context

        # 提取video和slice结构
        video_data = result.get("video", {})
        slice_data = result.get("slices", [])

        # 补充必要字段，确保与现有格式兼容
        video_data["video_id"] = video_id
        video_data["video_duration"] = video_duration
        video_data["asset_id"] = asset_id

        # 处理分片数据，补充必要字段
        understood_slices = []
        embed_slices = []
        for i, slice_item in enumerate(slice_data):
            slice_id = f"{video_id}_slice_{i}"
            # 补充分片基础字段
            slice_item["slice_id"] = slice_id
            slice_item["video_id"] = video_id
            slice_item["slice_index"] = i
            slice_item["asset_id"] = asset_id

            understood_slices.append(slice_item)

            # 准备向量化数据
            understanding_with_id = slice_item.copy()
            understanding_with_id["slice_id"] = slice_id
            understanding_with_id["video_id"] = video_id
            flattened = JsonFlattener.flatten(understanding_with_id)

            # 提取时间信息
            start_time = slice_item.get("creative_elements", {}).get("start_time", i * 10.0)
            end_time = slice_item.get("creative_elements", {}).get("end_time", (i + 1) * 10.0)

            embed_data = {
                "slice_id": slice_id,
                "content": flattened,
                "start_time": float(start_time),
                "end_time": float(end_time)
            }
            embed_slices.append(embed_data)

        # 准备整体向量化数据
        video_with_id = video_data.copy()
        video_with_id["video_id"] = video_id
        video_flattened = JsonFlattener.flatten(video_with_id)
        embed_video = {
            "video_id": video_id,
            "content": video_flattened
        }

        # 构建最终落库的ai_features结构
        ai_features = {
            "video_info": video_data,
            "slices": understood_slices,
            "parse_type": "direct_video",
            "parse_version": "1.0"
        }

        # 存储结果到上下文，使用标准键名
        context.set(constants.SLICE_DATA, understood_slices)
        context.set(constants.VIDEO_DATA, video_data)
        context.set(constants.UNDERSTOOD_SLICES, understood_slices)  # 兼容现有处理器
        context.set(constants.EMBED_SLICES, embed_slices)
        context.set(constants.EMBED_VIDEO, embed_video)
        context.set(constants.AI_FEATURES, ai_features)
        context.set("product_data", ai_features)  # 兼容AssetPersistProcessor

        # 记录处理统计
        context.metadata["direct_video_processing"] = {
            "video_id": video_id,
            "slice_count": len(understood_slices),
            "success": True
        }

        logger.info(f"Direct video understanding completed, video_id: {video_id}, slice_count: {len(understood_slices)}")

        return context
