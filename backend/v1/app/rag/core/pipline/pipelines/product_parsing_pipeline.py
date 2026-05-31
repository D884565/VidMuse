from typing import List, Optional
from backend.v1.app.rag.core.pipline.base import BasePipeline, BaseProcessor
from backend.v1.app.rag.core.pipline.processors import (
    ProductUnderstandingProcessor,
    ProductGenerateProcessor,
    SchemaValidationProcessor
)


class ProductParsingPipeline(BasePipeline):
    """
    商品解析流水线
    第二条流水线：图文理解 → 商品信息生成 → 结构校验
    """

    def __init__(self, custom_processors: List[BaseProcessor] = None,
                 product_schema_path: Optional[str] = None,
                 **kwargs):
        """
        初始化商品解析流水线

        :param custom_processors: 自定义处理器列表，可选，用于替换默认处理器
        :param product_schema_path: 商品校验Schema路径，可选，优先使用该路径而非默认模板
        :param kwargs: 其他参数，传递给父类
        """
        if custom_processors:
            processors = custom_processors
        else:
            # 默认处理器顺序
            if product_schema_path:
                # 使用自定义Schema路径
                validator = SchemaValidationProcessor(
                    schema_path=product_schema_path,
                    data_key="product_data",
                    valid_key="valid_product",
                    invalid_key="invalid_product",
                    summary_key="product_validation_summary",
                    id_field="SKU_ID"
                )
            else:
                # 使用默认product模板，自定义ID字段
                validator = SchemaValidationProcessor.for_product(
                    valid_key="valid_product",
                    invalid_key="invalid_product",
                    summary_key="product_validation_summary",
                    id_field="SKU_ID"
                )

            processors = [
                ProductUnderstandingProcessor(),
                ProductGenerateProcessor(),
                validator
            ]

        super().__init__(processors, pipeline_type="product", **kwargs)
