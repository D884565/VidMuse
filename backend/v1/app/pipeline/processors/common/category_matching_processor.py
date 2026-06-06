"""分类匹配处理器
将商品理解结果中的分类文本匹配到系统分类体系
"""
import logging
from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.product.service.category_matcher import ProductCategoryMatcher
logger = logging.getLogger(__name__)
class CategoryMatchingProcessor(BaseProcessor):
    """
    分类匹配处理器
    从商品理解结果中提取分类文本，匹配到product_categories表中的分类记录
    """

    def __init__(self):
        """初始化分类匹配处理器"""
        self.matcher = ProductCategoryMatcher()

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行分类匹配逻辑
        支持商品理解和视频理解两种场景：
        1. 商品场景：从product_data或product_understanding中提取分类
        2. 视频场景：从ai_features（视频整体理解结果）中提取分类
        :param context: 流水线上下文
        :return: 修改后的上下文，包含匹配到的分类信息
        """
        try:
            # 从上下文中获取数据（支持商品和视频两种场景）
            product_data = context.get("product_data", {})
            product_understanding = context.get("product_understanding", {})
            ai_features = context.get("ai_features", {})  # 视频整体理解结果
            product_id = context.get("product_id", "")
            video_id = context.get("video_id", "")

            # 提取分类文本，优先级：商品理解 > 视频理解 > 商品基础数据
            category_text = None
            source_id = product_id or video_id
            source_type = "product" if product_id else "video"

            # 1. 尝试从商品理解结果中获取分类信息（支持多种键名）
            if isinstance(product_understanding, dict):
                category_text = product_understanding.get("商品类别") or \
                               product_understanding.get("商品分类") or \
                               product_understanding.get("category") or \
                               product_understanding.get("分类")

            # 2. 尝试从视频整体理解结果中获取分类信息
            if not category_text and isinstance(ai_features, dict):
                video_basic_info = ai_features.get("视频基本信息", {})
                category_text = video_basic_info.get("商品分类") or \
                               video_basic_info.get("商品类别") or \
                               video_basic_info.get("category")

            # 3. 如果理解结果中没有，尝试从product_data中获取
            if not category_text and isinstance(product_data, dict):
                basic_info = product_data.get("basic_info", {})
                category_text = basic_info.get("category") or \
                               basic_info.get("商品分类") or \
                               basic_info.get("分类")

            if not category_text:
                logger.debug(f"未找到分类文本，{source_type}_id: {source_id}")
                return context

            logger.info(f"开始匹配分类，文本: '{category_text}', product_id: {product_id}")

            # 调用分类匹配服务
            match_result = self.matcher.match(str(category_text))

            if match_result:
                # 根据场景更新对应的数据结构
                if source_type == "product":
                    # 商品场景：更新product_data
                    if "basic_info" not in product_data:
                        product_data["basic_info"] = {}

                    product_data["basic_info"]["category_id"] = match_result["id"]
                    product_data["basic_info"]["category"] = match_result["name"]
                    product_data["basic_info"]["category_path"] = match_result["path"]
                    product_data["basic_info"]["category_level"] = match_result["level"]
                    product_data["basic_info"]["category_name_path"] = match_result["name_path"]

                    # 更新上下文
                    context.set("product_data", product_data)
                    logger.info(f"分类匹配成功，product_id: {source_id}, 分类: {match_result['name_path']} (ID: {match_result['id']})")
                else:
                    # 视频场景：更新ai_features中的视频基本信息
                    if "视频基本信息" not in ai_features:
                        ai_features["视频基本信息"] = {}

                    ai_features["视频基本信息"]["category_id"] = match_result["id"]
                    ai_features["视频基本信息"]["category_name"] = match_result["name"]
                    ai_features["视频基本信息"]["category_path"] = match_result["path"]
                    ai_features["视频基本信息"]["category_level"] = match_result["level"]
                    ai_features["视频基本信息"]["category_name_path"] = match_result["name_path"]

                    # 更新上下文
                    context.set("ai_features", ai_features)
                    logger.info(f"分类匹配成功，video_id: {source_id}, 分类: {match_result['name_path']} (ID: {match_result['id']})")

                # 公共字段更新
                context.set("category_id", match_result["id"])
                context.set("category_name", match_result["name"])
                context.set("category_path", match_result["path"])
                context.set("category_level", match_result["level"])
                context.set("category_name_path", match_result["name_path"])

            else:
                logger.warning(f"分类匹配失败，{source_type}_id: {source_id}, 分类文本: '{category_text}'")
                # 匹配失败时可以设置默认分类，或者保持原样
                context.set("category_match_failed", True)

        except Exception as e:
            logger.error(f"分类匹配处理器执行失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"分类匹配失败: {str(e)}"))

        return context
