import asyncio
import json
from typing import Dict, List

from volcenginesdkcore.interceptor.interceptors import request

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM, VideoUnderstandingRequest
from backend.providers.dto.schema import ChatRequest, ChatMessage, VideoUrlContent
from backend.v1.app.rag.core.pipline.utils import load_template
from backend.v1.app.rag.dao import AssetDAO


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
        self.llm_client =VolcanoLLM(key=None, model_name=None)
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

        :param context: 流水线上下文
        :return: 修改后的上下文，包含大模型理解结果
        """


        # 遍历片段url,并行解析片段
        slices = context.get("slices", [])
        if not slices or len(context.get("slices_count")) == 0:
            raise ValueError("No slices found in context")

        prompts = self.prompt_template.format(json_info=load_template("slice"))
        slices = list(dict())
        for i,slice_info in enumerate(slices):
            # 构建大模型请求
            response =  asyncio.run(self.llm_client.video_understanding(VideoUnderstandingRequest(
                video_url=slice_info,
                prompt=self.prompt_template,
                max_tokens=2048,
                temperature=0.7,
                top_p=0.9,
                model=""
            )))
            # 返回就解析
            # 直接添加模板
            slices.append(json.loads(response.content))
        # 合并理解结果到片段信息
        context.set("understood_slices", slices)

        return context
