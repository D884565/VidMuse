from typing import Dict, List, Any
import logging
from sqlalchemy.orm import Session

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.store.database.sync_database import get_db

logger = logging.getLogger(__name__)


class AssetPersistProcessor(BaseProcessor):
    """
    资产落库处理器
    将商品解析结果保存到asset表的ai_features字段中，更新解析状态
    """

    def __init__(self):
        """
        初始化资产落库处理器
        """
        pass

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行资产落库逻辑
        将生成的product_data作为AI特征更新到asset表中

        输入（从上下文获取）：
        - asset_id: int 资产ID（必填）
        - product_data: Dict 生成的商品结构化数据
        - parsing_status: str 解析状态，默认completed
        - parsing_error: str 错误信息（如果失败）

        :param context: 流水线上下文
        :return: 修改后的上下文
        """
        asset_id = context.get("asset_id")
        product_data = context.get("product_data", {})
        parsing_status = context.get("parsing_status", "completed")
        parsing_error = context.get("parsing_error", None)

        if not asset_id:
            raise ValueError("asset_id is required for persisting to asset table")

        try:
            # 获取数据库会话
            db: Session = next(get_db())

            # 构建更新数据
            update_data = {
                "ai_features": product_data,
                "parsing_status": parsing_status
            }

            if parsing_error:
                update_data["parsing_error"] = parsing_error

            # 更新资产记录
            updated_asset = AssetDAO.update_asset(db, int(asset_id), update_data)

            if not updated_asset:
                raise ValueError(f"Asset not found with id: {asset_id}")

            # 存储更新后的资产信息到上下文
            context.set("asset_info", updated_asset.to_dict())
            logger.info(f"商品数据成功落库到asset表，asset_id: {asset_id}")

            # 如果有product_id和分类信息，更新products表
            product_id = context.get("product_id")
            category_id = context.get("category_id")
            if product_id and category_id:
                try:
                    product_update_data = {
                        "category_id": category_id,
                        "category": context.get("category_name"),
                        "category_path": context.get("category_path")
                    }
                    # 更新商品记录
                    updated_product = ProductDAO.update_product(db, int(product_id), product_update_data)
                    if updated_product:
                        logger.info(f"商品分类信息成功更新，product_id: {product_id}, category_id: {category_id}")
                        context.set("product_info", updated_product.to_dict())
                except Exception as e:
                    logger.error(f"更新商品分类信息失败: {str(e)}", exc_info=True)
                    context.add_error(ValueError(f"更新商品分类信息失败: {str(e)}"))

        except Exception as e:
            logger.error(f"资产落库失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"资产落库失败: {str(e)}"))

        finally:
            if 'db' in locals() and db:
                db.close()

        return context
