from typing import Optional
import logging

from backend.v1.app.pipeline.base import BasePipeline, BaseProcessor, constants, PipelineContext
from backend.v1.app.pipeline.processors import SchemaValidationProcessor
from backend.v1.app.pipeline.processors.common.content_router_processor import ContentRouterProcessor
from backend.v1.app.pipeline.processors.common.asset_persist_processor import AssetPersistProcessor
from backend.v1.app.pipeline.processors.common.category_matching_processor import CategoryMatchingProcessor
from backend.v1.app.pipeline.processors.img.product_understanding_processor import ProductUnderstandingProcessor
from backend.v1.app.pipeline.processors.text.text_understanding_processor import TextUnderstandingProcessor
from backend.v1.app.pipeline.processors.video.video_product_understanding_processor import VideoProductUnderstandingProcessor
from backend.v1.app.pipeline.processors.img.product_generate_processor import ProductGenerateProcessor

logger = logging.getLogger(__name__)


class ProductParsingPipeline(BasePipeline):
    """
    商品解析流水线
    支持多模态输入：图片、文本、视频的任意组合
    流程：内容路由 → 对应理解处理 → 统一商品生成 → Schema校验 → 资产落库
    """

    def __init__(self,
                 product_schema_path: Optional[str] = None,
                 enable_persistence: bool = True,
                 persist_to_asset: bool = True,
                 **kwargs):
        """
        初始化商品解析流水线

        :param product_schema_path: 商品校验Schema路径，可选，优先使用该路径而非默认模板
        :param enable_persistence: 是否开启流水线执行记录持久化，默认True
        :param persist_to_asset: 是否将结果落库到asset表，默认True
        :param kwargs: 其他参数，传递给父类
        """
        # 构建商品校验器
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

        # 固定处理器顺序，不再支持自定义处理器
        processors = [
            # 第一阶段：内容路由，检测输入类型
            ContentRouterProcessor(),
            # 第二阶段：根据内容类型选择对应的理解处理器
            self._create_understanding_branch(),
            # 第三阶段：统一生成商品结构化数据
            ProductGenerateProcessor(),
            # 第四阶段：分类匹配，关联到系统分类体系
            CategoryMatchingProcessor(),
            # 第五阶段：Schema校验
            validator
        ]

        # 第五阶段：资产落库
        if persist_to_asset:
            processors.append(AssetPersistProcessor())

        super().__init__(
            processors,
            pipeline_type="product",
            enable_persistence=enable_persistence,
            **kwargs
        )

    def _create_understanding_branch(self) -> BaseProcessor:
        """
        创建理解分支处理器，根据内容类型动态选择对应的理解处理器
        """
        class UnderstandingBranchProcessor(BaseProcessor):
            """分支处理器，根据内容类型分发到对应的理解处理器"""
            def __init__(self):
                self.image_processor = ProductUnderstandingProcessor()
                self.text_processor = TextUnderstandingProcessor()
                self.video_processor = VideoProductUnderstandingProcessor()

            def process(self, context: PipelineContext) -> PipelineContext:
                has_image = context.get("has_image", False)
                has_text = context.get("has_text", False)
                has_video = context.get("has_video", False)
                content_types = context.get("content_types", [])

                logger.info(f"理解分支处理，内容类型: {content_types}")

                # 优先级：视频 > 图片 > 文本
                if has_video:
                    # 视频内容优先使用视频理解
                    return self.video_processor.process(context)
                elif has_image:
                    # 包含图片使用图片理解（支持图文混合）
                    return self.image_processor.process(context)
                elif has_text:
                    # 仅文本使用文本理解
                    return self.text_processor.process(context)
                else:
                    raise ValueError("No valid content type found for understanding")

        return UnderstandingBranchProcessor()
