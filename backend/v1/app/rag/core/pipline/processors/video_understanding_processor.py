import asyncio
import json
from typing import Dict, List

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import VideoUnderstandingRequest
from backend.v1.app.rag.core.pipline.utils import load_template
from backend.v1.app.rag.core.pipline.utils.json_flattener import JsonFlattener


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
        self.prompt_template = """
        请分析这个电商短视频片段，输出以下结构化信息：
        1. 模板名称：片段的内容类型名称（如：主播情绪开场、产品功能展示等）
        2. 模板类型：从以下选项选择：HOOK(钩子开场), PAIN_POINT(痛点描述), PRODUCT_SHOW(产品展示), TRUST_BUILD(信任建立), CTA(行动号召)
        3. 创作要素：
           - 画面：画面内容描述
           - 动作：人物动作描述
           - 台词：人物台词内容
           - 运镜：镜头运动方式
           - 时长：片段时长（如：3-5秒）
           - 情绪评分：0-1之间的浮点数，表示主播情绪兴奋程度
        4. 生成Prompt完整模板：可以直接用于AI视频生成的完整Prompt描述
        
        完整的json模板如下:
        {json_info}

        请严格按照JSON格式输出，不要有其他内容。
        """

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
                    response = asyncio.run(self.llm_client.video_understanding(VideoUnderstandingRequest(
                        video_url=slices_url[i],
                        prompt=prompt_template,
                        max_tokens=2048,
                        temperature=0.7,
                        top_p=0.9
                    )))
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
            # 扁平化理解结果，用于向量化
            # 先添加slice_id和video_id到理解结果中，再扁平化
            understanding_with_id = understanding_result.copy()
            understanding_with_id["slice_id"] = slice_data["slice_id"]
            understanding_with_id["video_id"] = video_id
            flattened = JsonFlattener.flatten(understanding_with_id)
            embed_slices.append(flattened)

        # 存储结果到上下文
        context.set("understood_slices", understood_slices)
        context.set("embed_slices", embed_slices)
        # 将视频封面图列表存入上下文，供后续图像向量化使用
        context.set("slice_cover_urls", images_url)

        return context
