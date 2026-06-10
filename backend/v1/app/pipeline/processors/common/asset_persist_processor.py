from typing import Dict, List, Any
import json
import logging
from sqlalchemy.orm import Session

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.admin.video_library.dao.video_library_dao import VideoLibraryDAO
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

        # 类型安全校验：确保product_data是字典类型
        if isinstance(product_data, str):
            try:
                logger.warning(f"product_data是字符串类型，尝试解析为JSON: {product_data[:500]}...")
                product_data = json.loads(product_data)
            except json.JSONDecodeError as e:
                error_msg = f"product_data是字符串类型且无法解析为JSON: {str(e)}"
                logger.error(error_msg)
                context.add_error(ValueError(error_msg))
                return context

        if not isinstance(product_data, dict):
            error_msg = f"product_data类型错误，期望字典，实际: {type(product_data)}"
            logger.error(error_msg)
            context.add_error(ValueError(error_msg))
            return context

        # 确保ai_features也是字典类型（兼容直接使用ai_features字段的情况）
        ai_features = context.get("ai_features", product_data)
        if isinstance(ai_features, str):
            try:
                logger.warning(f"ai_features是字符串类型，尝试解析为JSON")
                ai_features = json.loads(ai_features)
                context.set("ai_features", ai_features)
            except json.JSONDecodeError as e:
                logger.warning(f"ai_features解析失败，将使用product_data代替: {str(e)}")

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

            # 同步状态到业务表
            business_id = context.get("business_id")
            business_type = context.get("business_type")
            if business_id and business_type:
                if business_type in ["ProductService", "product"]:
                    # 如果有product_id，更新products表
                    product_id = context.get("product_id")
                    AssetDAO.update_asset(db,int(asset_id),update_data)
                    # 如果有分类信息，也更新分类
                    category_id = context.get("category_id")
                    if category_id:
                        product_data = update_data.update({
                            "category_id": category_id,
                            "category": context.get("category_name"),
                            "category_path": context.get("category_path")
                        })
                    ProductDAO.update_product(db,int(product_id),product_data)
                elif business_type in ["VideoLibraryService", "video_library"]:
                    video_id = context.get("video_id")
                    VideoLibraryDAO.update(db,video_id,update_data) 
            
            
            
            db.commit()

        except Exception as e:
            logger.error(f"资产落库失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"资产落库失败: {str(e)}"))

        finally:
            if 'db' in locals() and db:
                db.close()

        return context
