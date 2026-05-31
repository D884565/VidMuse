from typing import Dict, List
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext


class ProductGenerateProcessor(BaseProcessor):
    """
    商品JSON生成处理器
    根据大模型理解结果生成符合模板要求的商品结构化数据，保存在上下文中
    处理图+文信息的解析
    """

    def __init__(self):
        """
        初始化商品生成处理器
        """
        pass

    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行商品JSON生成逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含生成的商品数据
        """
        # 从上下文中获取商品理解结果
        product_understanding = context.get("product_understanding", {})
        product_id = context.get("product_id")

        # 构建商品结构化数据（预留逻辑，目前直接透传理解结果）
        product_data = product_understanding
        product_data["product_id"] = product_id

        # 存储到上下文
        context.set("product_data", product_data)
        context.set("product_file", None)  # 保留字段，兼容旧接口
        context.metadata["product_generated"] = True

        return context
