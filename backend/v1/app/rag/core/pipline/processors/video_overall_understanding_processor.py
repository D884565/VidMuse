import json
from typing import Dict, List
from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage, TextContent, TextUnderstandingRequest
from backend.v1.app.rag.core.pipline.utils import load_template
from backend.v1.app.rag.core.pipline.utils.json_flattener import JsonFlattener


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
        self.llm_client = llm_client or VolcanoLLM()
        self.prompt_template = """
        请基于以下视频分片的解析结果，对整个视频进行整体分析，输出结构化的视频信息，严格按照JSON格式返回。

        需要包含以下字段：
        1. 视频基本信息：
           - video_id: 视频ID
           - 商品名称: 视频推广的商品名称
           - 目标人群: 视频的目标受众
           - 总时长_ms: 视频总时长（毫秒）
           - 原片核心文案: 视频中出现的核心台词数组

        2. 片段索引列表：直接使用输入中的segment_list数组，无需修改

        3. 片段间关系：
           - 转场序列: 各片段之间的转场方式数组，如["硬切", "叠化"]
           - 情绪曲线: 视频的情绪变化曲线数组，如["高涨→平稳", "平稳→微升"]
           - 视觉节奏: 整体视觉节奏描述
           - BGM节奏匹配: BGM与画面的匹配情况描述
        

        请严格按照如下json格式输出解析内容，请保证所有字段完整。
        {json_template}
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频整体理解逻辑

        :param context: 流水线上下文，需要包含 aggregated_segments 字段
        :return: 修改后的上下文，包含视频整体理解结果
        """
        slices = context.get("understood_slices")

        if not slices:
            raise ValueError("No aggregated segments found in context")

        # 将解析json铺平合成文本
        segment_info_str = ''.join([JsonFlattener.flatten(s) for s in slices])

        # json模板信息注入到prompt
        prompts = self.prompt_template.format(json_template=load_template("video"))

        # 构建大模型请求
        response = self.llm_client.text_understanding(TextUnderstandingRequest(prompt=prompts, text=segment_info_str))
        resolve = json.loads(response.content)
        context.set("ai_features",resolve)
        context.set("embed_video",JsonFlattener.flatten(resolve))
        return context
