from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, VideoUrlContent


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
        self.llm_client = llm_client or VolcanoLLM()
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

        请严格按照JSON格式输出，不要有其他内容。
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频理解逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含大模型理解结果
        """
        slices = context.get("slices", [])
        video_path = context.get("video_path")

        if not slices:
            raise ValueError("No slices found in context")
        if not video_path:
            raise ValueError("video_path is required in context")

        understood_slices: List[Dict] = []

        for slice_info in slices:
            # 构建大模型请求
            request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content=self.prompt_template),
                    ChatMessage(
                        role="user",
                        content=[
                            VideoUrlContent(url=video_path, time_range=slice_info["time_range"])
                        ]
                    )
                ]
            )

            # 调用大模型（Mock：实际调用时取消注释）
            # response = self.llm_client.chat(request)
            # understanding = response.content

            # Mock 响应（临时使用，实际调用时替换为真实响应）
            understanding = {
                "模板名称": "主播情绪开场",
                "模板类型": "HOOK",
                "机制": "emotional_resonance",
                "总结": "主播以兴奋的情绪打招呼，吸引用户注意力",
                "创作要素": {
                    "画面": "主播半身中景，明亮直播间，暖色调",
                    "动作": "挥手打招呼，表情兴奋",
                    "台词": "家人们，谁懂啊！",
                    "运镜": "固定机位，平视角度",
                    "时长": "3-5秒",
                    "情绪评分": 0.8
                },
                "一致性": {
                    "商品": [],
                    "置信度": 0.9
                },
                "生成Prompt完整模板": "中景固定机位，年轻女性主播在明亮直播间兴奋挥手打招呼，暖色调布光，专业电商质感，高清"
            }

            # 合并理解结果到片段信息
            understood_slice = {**slice_info, "understanding": understanding}
            understood_slices.append(understood_slice)

        context.set("understood_slices", understood_slices)
        context.metadata["understanding_count"] = len(understood_slices)

        return context
