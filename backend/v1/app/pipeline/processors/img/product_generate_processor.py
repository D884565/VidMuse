from typing import Dict, List, Any
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
import logging

logger = logging.getLogger(__name__)


class ProductGenerateProcessor(BaseProcessor):
    """
    商品JSON生成处理器
    根据大模型理解结果生成符合模板要求的商品结构化数据，保存在上下文中
    统一处理图片、文本、视频三种来源的理解结果
    """

    def __init__(self):
        """
        初始化商品生成处理器
        """
        pass

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行商品JSON生成逻辑
        统一处理不同来源的理解结果，生成标准product.json格式

        :param context: 流水线上下文
        :return: 修改后的上下文，包含生成的商品数据
        """
        # 从上下文中获取商品理解结果
        product_understanding = context.get("product_understanding", {})
        product_id = context.get("product_id", "")
        asset_id = context.get("asset_id", "")  # 资产ID，如果存在
        content_types = context.get("content_types", [])

        if not product_understanding:
            raise ValueError("product_understanding is required for generating product data")

        # 构建标准商品结构化数据
        product_data = {
            # 基础信息
            "product_id": product_id,
            "asset_id": asset_id,
            "source_types": content_types,  # 数据来源类型：image/text/video

            # 商品核心信息
            "basic_info": {
                "product_name": product_understanding.get("商品名称", product_understanding.get("product_name", "")),
                "description": product_understanding.get("商品介绍", product_understanding.get("description", "")),
                "category": product_understanding.get("商品分类", product_understanding.get("category", "general")),
                "brand": product_understanding.get("品牌", product_understanding.get("brand", "")),
                "target_audience": product_understanding.get("目标人群", product_understanding.get("target_audience", "")),
                "scenarios": product_understanding.get("使用场景", product_understanding.get("scenarios", []))
            },

            # 卖点信息
            "selling_points": product_understanding.get("核心卖点", product_understanding.get("selling_points", [])),

            # 价格信息
            "price_info": {
                "original_price": float(product_understanding.get("价格信息", {}).get("原价", product_understanding.get("original_price", 0))),
                "current_price": float(product_understanding.get("价格信息", {}).get("现价", product_understanding.get("current_price", 0))),
                "discount_info": product_understanding.get("价格信息", {}).get("优惠信息", product_understanding.get("discount_info", ""))
            },

            # 商品参数
            "parameters": product_understanding.get("商品参数", product_understanding.get("parameters", {})),

            # SKU信息
            "skus": product_understanding.get("SKU信息", product_understanding.get("skus", [])),

            # 附属信息
            "tags": product_understanding.get("标签", product_understanding.get("tags", [])),
            "keywords": product_understanding.get("关键词", product_understanding.get("keywords", [])),

            # 扩展信息
            "ext_info": {}
        }

        # 添加视频相关信息如果来源是视频
        if "video" in content_types:
            product_data["ext_info"]["video_info"] = product_understanding.get("视频分析", {})

        # 存储到上下文
        context.set("product_data", product_data)
        context.set("product_file", None)  # 保留字段，兼容旧接口
        context.metadata["product_generated"] = True

        logger.info(f"商品JSON生成完成，product_id: {product_id}, 来源类型: {content_types}")

        return context
