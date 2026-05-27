from typing import Dict, List, Union

from backend.v1.app.rag.core.pipline.base import BaseProcessor, PipelineContext
from backend.providers import VolcanoLLM, ImageUnderstandingRequest
from backend.providers.dto.schema import (
    ChatRequest,
    ChatMessage,
    TextContent,
    ImageUrlContent,
    MultimodalContent
)


class ProductUnderstandingProcessor(BaseProcessor):
    """
    商品理解处理器
    接收图文混合内容，调用大模型分析商品信息
    """

    def __init__(self, llm_client=None):
        """
        初始化商品理解处理器

        :param llm_client: 大模型客户端，默认使用VolcanoLLM
        """
        self.llm_client = llm_client or VolcanoLLM()
        self.prompt_template = """
        请分析以下图文内容，输出商品的结构化信息，严格按照JSON格式返回，不要有其他内容。
        需要包含以下字段：
        1. 商品基础信息：包含商品名称、商品类目预测、品牌信息、SKU_ID
        2. 目标人群：包含核心人群（数组）、消费心理（数组）、使用场景（数组）
        3. 卖点列表：数组，每个元素包含名称、描述、优先级、视频表现手法、口播参考
        4. 物理属性：包含通用属性（材质成分、季节等）、类目专属扩展字段（根据商品类目灵活添加）
        5. 价格与服务：包含原价、现价、促销策略、价格锚点、服务保障（数组）
        6. 视觉资产：包含商品主图、商品细节图（数组）、使用场景图（数组）、品牌VI色（数组）
        7. 竞争差异化：包含对比维度、独家优势（数组）
        8. 合规限制：包含禁用话术（数组）、必须声明（数组）
        
        
        {

  "目标人群": {
    "核心人群": ["25-35岁女性", "梨形身材", "职场新人"],
    "消费心理": ["追求性价比", "注重颜值", "社交分享欲强"],
    "使用场景": ["日常通勤", "周末约会", "拍照打卡"]
  },

  "卖点列表": [
    {
      "名称": "法式收腰设计",
      "描述": "高腰线+微褶皱处理，完美包容小肚子",
      "优先级": "P0",
      "视频表现手法": "模特侧面转圈特写 / 拉扯面料展示弹性",
      "口播参考": "姐妹们看这个收腰，吃撑了也不勒肚子！"
    }
  ],

  "物理属性": {
    "通用属性": {
      "材质成分": "100%聚酯纤维",
      "季节": "春夏"
    },
    "类目专属扩展字段": {
      "服装版型": "A字裙",
      "尺码范围": "S-XL",
      "颜色分类": ["樱花粉", "雾霾蓝"]
    }
  },

  "价格与服务": {
    "原价": 299,
    "现价": 159,
    "促销策略": "限时直降140元",
    "价格锚点": "线下专柜同款399元",
    "服务保障": ["赠送运费险", "7天无理由退换", "48小时发货"]
  },

  "竞争差异化": {
    "对比维度": "同价位竞品多为直筒无收腰",
    "独家优势": ["同价位唯一收腰设计", "独家定制碎花图案"]
  },

  "合规限制": {
    "禁用话术": ["最显瘦", "全网第一", "绝对不褪色"],
    "必须声明": ["效果因人而异", "图片仅供参考"]
  }
}

        如果信息不足，可以留空或生成合理的模拟值，但必须保证结构完整。
        """

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行商品理解逻辑

        :param context: 流水线上下文，需要包含 multimodal_content 字段
        :return: 修改后的上下文，包含商品理解结果
        """
        images = context.get("images")
        description = context.get("description", "")

        if not description and not images:
            raise ValueError("multimodal_content is required in context")

        # 构建大模型请求
        request = ImageUnderstandingRequest(
            prompt=description,
            image_url=images,
            max_tokens=1024,
            temperature=0.7,
            top_p=0.9,
            model="_llama2_7b_chat_v2",
        )
        response = self.llm_client.image_understanding( request)
        context.set("product_understanding", response)


        return context
