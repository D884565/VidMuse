"""商品业务逻辑层

职责：处理商品相关的业务逻辑，包括创建、查询、更新、删除商品。
权限校验在此层完成（只有商品所有者或管理员可修改/删除）。
不直接操作数据库，通过 ProductDAO 访问数据层。
"""
import json
from typing import Optional, List, Dict, Any
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import ValidationError

from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.product.dao.product_asset_dao import ProductAssetDAO
from backend.v1.app.product.dao.schema import product_to_dict, ProductCreateRequest, ProductUpdateRequest, _parse_json_field
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import (
    RESOURCE_NOT_FOUND,
    FORBIDDEN,
    PARAM_ERROR,
)
from backend.v1.app.common.parsing.base_parsing_service import BaseParsingService
from backend.v1.app.pipeline.base import BasePipeline

# 导入移到函数内部，避免循环导入
# from backend.v1.app.pipeline.factory.pipeline_factory import PipelineFactory
# AssetService 导入移到函数内部，避免循环导入


class ProductService(BaseParsingService):
    """商品业务逻辑层
    继承BaseParsingService，复用统一解析框架能力
    """

    # 实现BaseParsingService的抽象方法
    def get_pipeline(self, context: Dict[str, Any]) -> BasePipeline:
        """根据资产类型动态选择对应的解析流水线
        优先级：视频 > 图片 > 音频 > 文本
        """
        from backend.v1.app.pipeline.factory.pipeline_factory import PipelineFactory

        asset_type = context.get("asset_type")
        if asset_type:
            return PipelineFactory.get_pipeline_for_asset_type(
                asset_type=asset_type,
                persist_to_asset=True,
                enable_persistence=True
            )
        # 没有指定资产类型，默认使用商品解析流水线
        from backend.v1.app.pipeline.pipelines.product_parsing_pipeline import ProductParsingPipeline
        return ProductParsingPipeline(
            persist_to_asset=True,
            enable_persistence=True
        )

    def get_asset_id(self, db: Session, business_id: int, context: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """根据商品ID获取要解析的资产ID
        规则：
        1. 如果context中指定了selected_asset_id，优先使用
        2. 否则优先找角色为main的资产
        3. 没有main资产则取第一个关联资产
        4. 没有关联资产返回None
        """
        context = context or {}
        # 检查是否在context中指定了资产ID
        selected_asset_id = context.get('selected_asset_id')
        if selected_asset_id:
            return selected_asset_id

        # 没有指定，按默认规则查找
        product = ProductDAO.get_product_by_id(db, business_id, include_assets=True)
        if not product or not product.assets:
            return None

        # 先找main角色的资产
        main_assets = ProductAssetDAO.get_assets_by_product_id_and_role(db, business_id, "main")
        if main_assets:
            return main_assets[0].id

        # 没有main资产，取第一个
        return product.assets[0].id

    def sync_status(self, db: Session, business_id: int, asset: Any) -> None:
        """同步资产状态到商品表"""
        update_fields = {
            "execution_id": asset.execution_id,
            "parsing_status": asset.parsing_status,
            "parsing_error": asset.parsing_error,
        }

        # 如果有AI特征，同步到商品表
        if asset.ai_features:
            update_fields["ai_features"] = asset.ai_features

        ProductDAO.update_product(db, business_id, update_fields)

    @staticmethod
    def create_product(db: Session, user_id: int, data: ProductCreateRequest) -> dict:
        """创建商品

        :param db: 数据库会话
        :param user_id: 当前登录用户ID（作为商品所有者）
        :param data: 创建商品请求数据
        :return: 创建结果（含 id、name 等基本信息）
        """
        product_data = data.model_dump(exclude_unset=True)
        product_data["user_id"] = user_id  # 设置商品所有者

        # 处理分类关联
        if "category_id" in product_data and product_data["category_id"] is not None:
            category = ProductCategoryDAO.get_category_by_id(db, product_data["category_id"])
            if not category:
                raise BusinessException(PARAM_ERROR, f"分类ID {product_data['category_id']} 不存在")
            if category.level != 3:
                raise BusinessException(PARAM_ERROR, "只能选择三级分类关联商品")

            # 自动填充分类名称和路径
            product_data["category"] = category.name
            product_data["category_path"] = category.path

        try:
            # 开启事务，确保商品创建和资产关联的原子性
            with db.begin_nested():
                product = ProductDAO.create_product(db, product_data)

                # 处理资产关联
                asset_ids = data.asset_ids
                if asset_ids:
                    # 验证所有资产是否存在且属于当前用户
                    for asset_id in asset_ids:
                        asset = AssetDAO.get_asset_by_id(db, asset_id)
                        if not asset:
                            raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 不存在")
                        # 校验资产所属权
                        if asset.user_id != user_id:
                            raise BusinessException(FORBIDDEN, f"无权限操作资产ID {asset_id}")

                    # 批量创建关联
                    ProductAssetDAO.create_product_assets_batch(
                        db,
                        product_id=product.id,
                        asset_ids=asset_ids,
                        roles=data.asset_roles
                    )
            db.commit()
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

        result = {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "category_id": product.category_id,
            "description": product.description,
            "price": float(product.price) if product.price is not None else None,
            "main_image_url": product.main_image_url,
            "user_id": product.user_id,
            "auto_parse": product.auto_parse,
            "asset_ids": asset_ids,
            "created_at": product.created_at.isoformat() if product.created_at else "",
            "updated_at": product.updated_at.isoformat() if product.updated_at else "",
        }

        return result

    @staticmethod
    def get_product(db: Session, product_id: int, current_user_id: int, include_category_info: bool = True, include_assets: bool = True) -> dict:
        """获取商品详情

        :param db: 数据库会话
        :param product_id: 商品ID
        :param current_user_id: 当前用户ID
        :param include_category_info: 是否包含完整分类信息
        :param include_assets: 是否包含关联的资产信息
        :return: 商品详细信息字典
        :raises BusinessException: 商品不存在时抛出 RESOURCE_NOT_FOUND
        """
        product = ProductDAO.get_product_by_id(db, product_id, include_category=include_category_info, include_assets=include_assets)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        return product_to_dict(product, include_category_info=include_category_info, include_assets=include_assets)

    @staticmethod
    def update_product(db: Session, product_id: int, user_id: int, data: ProductUpdateRequest) -> dict:
        """更新商品信息（仅商品所有者可操作）

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID（用于权限校验）
        :param data: 更新数据
        :return: 更新结果
        :raises BusinessException: 商品不存在或无权限时抛出异常
        """
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        # 权限校验：只有商品所有者可修改（user_id 为 NULL 的公共商品除外）
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return {"id": product.id, "updated_at": product.updated_at.isoformat() if product.updated_at else ""}

        try:
            # 开启事务，确保分类更新等操作的原子性
            with db.begin_nested():
                # 处理分类关联
                if "category_id" in update_data and update_data["category_id"] is not None:
                    category = ProductCategoryDAO.get_category_by_id(db, update_data["category_id"])
                    if not category:
                        raise BusinessException(PARAM_ERROR, f"分类ID {update_data['category_id']} 不存在")
                    if category.level != 3:
                        raise BusinessException(PARAM_ERROR, "只能选择三级分类关联商品")

                    # 自动填充分类名称和路径
                    update_data["category"] = category.name
                    update_data["category_path"] = category.path
                elif "category_id" in update_data and update_data["category_id"] is None:
                    # 清空分类关联
                    update_data["category_path"] = None

                product = ProductDAO.update_product(db, product_id, update_data)
            db.commit()
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

        return {
            "id": product.id,
            "updated_at": product.updated_at.isoformat() if product.updated_at else "",
        }

    @staticmethod
    def delete_product(db: Session, product_id: int, user_id: int) -> None:
        """删除商品（仅商品所有者可操作）

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID（用于权限校验）
        :raises BusinessException: 商品不存在或无权限时抛出异常
        """
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        try:
            # 开启事务，确保删除商品和关联资产的原子性
            with db.begin_nested():
                # 先删除商品资产关联
                from backend.v1.app.product.dao.product_asset_dao import ProductAssetDAO
                ProductAssetDAO.delete_all_by_product_id(db, product_id)
                # 再删除商品
                ProductDAO.delete_product(db, product_id)
            db.commit()
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

    @staticmethod
    def parse_product(db: Session, product_id: int, user_id: int, force: bool = False, asset_id: Optional[int] = None) -> str:
        """手动触发商品解析

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID（用于权限校验）
        :param force: 是否强制重新解析
        :param asset_id: 可选，指定要解析的资产ID，不传则优先解析主资产
        :return: 解析执行ID
        :raises BusinessException: 商品不存在或无权限时抛出异常
        """
        # 1. 权限校验和参数验证
        product = ProductDAO.get_product_by_id(db, product_id, include_assets=True)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 2. 验证指定的asset_id是否关联到此商品且属于当前用户
        target_asset = None
        if asset_id:
            target_asset = next((a for a in product.assets if a.id == asset_id), None)
            if not target_asset:
                raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 未关联到此商品")
            # 校验资产所属权
            if target_asset.user_id != user_id:
                raise BusinessException(FORBIDDEN, f"无权限操作资产ID {asset_id}")

        # 3. 构建上下文参数
        images = _parse_json_field(product.images, [])
        description = product.description or ""
        context = {
            "user_id": user_id,
            "product_id": product_id,
            "description": description,
            "images": images,
            "selected_asset_id": asset_id,  # 传递指定的资产ID给get_asset_id方法
            "business_type": "ProductService",
        }
        if target_asset:
            context["asset_type"] = target_asset.type

        # 4. 调用基类统一解析流程
        service = ProductService()
        success = service.trigger_parsing(db, product_id, force=force, context=context)

        if not success:
            updated_product = ProductDAO.get_product_by_id(db, product_id)
            if updated_product.parsing_status == "failed":
                raise BusinessException(PARAM_ERROR, f"解析失败: {updated_product.parsing_error}")

        # 5. 提取解析结果中的描述和AI特征回写到商品表
        # TODO: 后续可以优化为通过流水线后置处理器处理
        updated_product = ProductDAO.get_product_by_id(db, product_id)
        execution_id = updated_product.execution_id

        if execution_id:
            try:
                # 获取流水线执行结果
                from backend.v1.app.pipeline.pipelines.product_parsing_pipeline import ProductParsingPipeline
                status = ProductParsingPipeline.get_execution_status(execution_id)
                if status and status.get("status") == "completed" and status.get("result"):
                    result_data = status["result"].get("data") or {}
                    update_fields = {}

                    # 优先提取商品描述（仅当原有描述为空时）
                    if not product.description:
                        # 尝试从商品解析结果中获取
                        product_data = result_data.get("product_data", {})
                        generated_desc = (product_data.get("basic_info") or {}).get("description", "")
                        if not generated_desc:
                            # 尝试从音频解析结果中获取语音识别文本
                            generated_desc = result_data.get("transcript", "") or (result_data.get("ai_features") or {}).get("transcript", "")
                        if generated_desc and isinstance(generated_desc, str) and generated_desc.strip():
                            update_fields["description"] = generated_desc.strip()

                    # 更新AI特征字段（如果有）
                    if "ai_features" in result_data:
                        update_fields["ai_features"] = json.dumps(result_data["ai_features"], ensure_ascii=False)
                    # 兼容商品解析结果中的AI特征
                    elif "product_data" in result_data:
                        product_ai_features = result_data["product_data"].get("ai_features")
                        if product_ai_features:
                            update_fields["ai_features"] = json.dumps(product_ai_features, ensure_ascii=False)

                    # 有需要更新的字段则执行更新
                    if update_fields:
                        ProductDAO.update_product(db, product_id, update_fields)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"获取解析结果回写商品表失败: {str(e)}")

        # 返回最新的execution_id
        updated_product = ProductDAO.get_product_by_id(db, product_id)
        return updated_product.execution_id

    @staticmethod
    def get_parsing_progress(db: Session, product_id: int, user_id: int) -> dict:
        """
        查询商品解析进度
        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID
        :return: 进度信息
        """
        # 权限校验保留
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 调用基类的进度查询逻辑
        service = ProductService()
        progress = service.get_parsing_progress(db, product_id)

        if not progress:
            # 基础信息兜底
            return {
                "product_id": product.id,
                "parsing_status": product.parsing_status,
                "execution_id": product.execution_id,
                "parsing_error": product.parsing_error,
                "ai_features": product.ai_features,
                "description": product.description,
                "updated_at": product.updated_at.isoformat() + "Z" if product.updated_at else None
            }

        # 转换返回格式，保持接口兼容
        progress["product_id"] = progress.pop("business_id")
        progress["ai_features"] = product.ai_features
        progress["description"] = product.description

        # 补充详细进度信息（基类返回的已经包含了，这里确保格式一致）
        if product.execution_id and "progress_detail" not in progress:
            try:
                from backend.v1.app.pipeline.pipelines.product_parsing_pipeline import ProductParsingPipeline
                execution_status = ProductParsingPipeline.get_execution_status(product.execution_id)
                if execution_status:
                    progress["progress_detail"] = {
                        "current_processor": execution_status["current_processor_index"] + 1,
                        "total_processors": execution_status["total_processors"],
                        "progress_percent": round((execution_status["current_processor_index"] + 1) / execution_status["total_processors"] * 100, 2) if execution_status["total_processors"] > 0 else 0,
                        "status": execution_status["status"],
                        "created_at": execution_status["created_at"],
                        "updated_at": execution_status["updated_at"]
                    }
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"查询详细进度失败: {str(e)}")

        return progress

    @staticmethod
    def retry_parsing(db: Session, product_id: int, user_id: int) -> str:
        """
        重试失败的商品解析
        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID
        :return: 执行ID
        """
        # 权限校验保留
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 检查状态
        if product.parsing_status not in ["failed", None]:
            raise BusinessException(PARAM_ERROR, "只有失败的解析任务可以重试")

        # 调用基类的重试逻辑
        service = ProductService()
        success = service.retry_parsing(db, product_id)

        if not success:
            updated_product = ProductDAO.get_product_by_id(db, product_id)
            raise BusinessException(PARAM_ERROR, f"重试失败: {updated_product.parsing_error}")

        # 返回最新的execution_id
        updated_product = ProductDAO.get_product_by_id(db, product_id)
        return updated_product.execution_id

    @staticmethod
    async def upload_and_create_product(
        db: Session,
        background_tasks: BackgroundTasks,
        user_id: int,
        files: List[UploadFile],
        product_info: dict,
        asset_roles: Optional[dict] = None
    ) -> dict:
        """
        上传文件并创建商品（业务逻辑封装）
        :param db: 数据库会话
        :param background_tasks: 后台任务对象
        :param user_id: 当前用户ID
        :param files: 上传的文件列表
        :param product_info: 商品信息字典
        :param asset_roles: 资产角色映射，key为文件索引（从0开始），value为角色
        :return: 创建结果
        """
        # 导入移到这里避免循环依赖
        from backend.v1.app.assets.service.asset_service import AssetService

        try:
            req = ProductCreateRequest(**product_info)
        except ValidationError as e:
            raise BusinessException(PARAM_ERROR, f"商品信息校验失败: {str(e)}")

        # 1. 上传所有文件，创建资产
        asset_ids = []
        asset_role_map = {}
        for index, file in enumerate(files):
            # 检测文件类型
            asset_type = AssetService.detect_asset_type(file)

            # 上传资产（跳过自动解析，后面统一处理）
            asset_result = await AssetService.upload_user_asset(
                db=db,
                background_tasks=background_tasks,
                file=file,
                type=asset_type,
                title=f"{req.name}_素材_{index+1}",
                source_type=0,  # 用户上传
                skip_analysis=True,  # 跳过自动解析，由商品解析统一处理
                user_id=user_id,
            )
            asset_ids.append(asset_result["id"])
            # 设置资产角色
            role = asset_roles.get(index, "main" if index == 0 else "image") if asset_roles else ("main" if index == 0 else "image")
            asset_role_map[asset_result["id"]] = role

        try:
            # 开启事务，确保资产创建和商品创建的原子性
            with db.begin_nested():
                # 2. 创建商品并关联资产（create_product方法中已经包含资产所属权校验和嵌套事务）
                req.asset_ids = asset_ids
                req.asset_roles = asset_role_map
                product_result = ProductService.create_product(db, user_id, req)
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            # 注意：已经上传到对象存储的文件需要异步清理，这里不处理
            raise e

        # 3. 如果需要自动解析，添加后台任务
        if req.auto_parse and asset_ids:
            def run_parse():
                try:
                    # 创建新的数据库会话用于后台任务
                    from backend.store.database.sync_database import get_db
                    db_bg = next(get_db())
                    # 解析主资产
                    main_asset_id = next((aid for aid, role in asset_role_map.items() if role == "main"), asset_ids[0])
                    ProductService.parse_product(db_bg, product_result["id"], user_id, asset_id=main_asset_id)
                    db_bg.commit()  # 确保解析结果持久化
                    db_bg.close()
                except Exception as e:
                    # 后台任务失败只记录日志，不影响主流程
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"商品自动解析失败: {e}")

            background_tasks.add_task(run_parse)
            product_result["parse_execution_id"] = None  # 后台任务暂时不返回execution_id

        return product_result

    @staticmethod
    def list_products(
        db: Session,
        user_id: Optional[int] = None,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        category1: Optional[int] = None,
        category2: Optional[int] = None,
        category3: Optional[int] = None,
        platform: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        only_public: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取商品列表

        返回当前用户的商品 + 平台公共商品（user_id IS NULL），支持多维度筛选和分页。

        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param keyword: 搜索关键词
        :param category: 分类名称筛选（兼容旧版）
        :param category1: 一级分类ID筛选
        :param category2: 二级分类ID筛选
        :param category3: 三级分类ID筛选
        :param platform: 平台筛选
        :param min_price: 最低价格
        :param max_price: 最高价格
        :param only_public: 是否只看公共商品
        :param page: 页码
        :param page_size: 每页数量
        :return: 分页结果字典
        """
        total, products = ProductDAO.list_products(
            db, user_id=user_id, keyword=keyword, category=category,
            category1=category1, category2=category2, category3=category3,
            platform=platform, min_price=min_price, max_price=max_price,
            only_public=only_public, page=page, page_size=page_size,
        )
        product_list = []
        for p in products:
            product_list.append({
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "description": p.description,
                "price": float(p.price) if p.price is not None else None,
                "main_image_url": p.main_image_url,
                "platform": p.platform,
                "auto_parse": p.auto_parse,
                "is_public": p.user_id is None,  # user_id 为空表示平台公共商品
                "created_at": p.created_at.isoformat() if p.created_at else "",
            })
        return {
            "list": product_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }

    @staticmethod
    def add_product_assets(
        db: Session,
        product_id: int,
        user_id: int,
        asset_ids: List[int],
        asset_roles: Optional[Dict[int, str]] = None
    ) -> dict:
        """批量添加商品关联资产

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID
        :param asset_ids: 资产ID列表
        :param asset_roles: 资产角色映射，key为asset_id，value为角色
        :return: 关联结果
        :raises BusinessException: 商品不存在、无权限、资产不存在或无权限操作资产时抛出
        """
        # 校验商品存在且用户有权限
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 校验资产ID列表不为空
        if not asset_ids:
            raise BusinessException(PARAM_ERROR, "资产ID列表不能为空")

        # 去重资产ID
        asset_ids = list(set(asset_ids))
        asset_roles = asset_roles or {}

        try:
            # 开启事务
            with db.begin_nested():
                # 验证所有资产是否存在且属于当前用户
                for asset_id in asset_ids:
                    asset = AssetDAO.get_asset_by_id(db, asset_id)
                    if not asset:
                        raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 不存在")
                    if asset.user_id != user_id:
                        raise BusinessException(FORBIDDEN, f"无权限操作资产ID {asset_id}")

                # 批量创建关联
                ProductAssetDAO.create_product_assets_batch(
                    db,
                    product_id=product_id,
                    asset_ids=asset_ids,
                    roles=asset_roles
                )
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

        return {
            "product_id": product_id,
            "added_asset_ids": asset_ids,
            "message": "资产关联成功"
        }

    @staticmethod
    def remove_product_asset(
        db: Session,
        product_id: int,
        asset_id: int,
        user_id: int,
        role: Optional[str] = None
    ) -> dict:
        """删除商品关联资产

        :param db: 数据库会话
        :param product_id: 商品ID
        :param asset_id: 资产ID
        :param user_id: 当前用户ID
        :param role: 可选，指定要删除的角色，若不传则删除该资产的所有关联
        :return: 删除结果
        :raises BusinessException: 商品不存在、无权限、关联不存在时抛出
        """
        # 校验商品存在且用户有权限
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 校验资产存在且属于当前用户
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 不存在")
        if asset.user_id != user_id:
            raise BusinessException(FORBIDDEN, f"无权限操作资产ID {asset_id}")

        try:
            # 开启事务
            with db.begin_nested():
                # 删除关联
                success = ProductAssetDAO.delete_product_asset(db, product_id, asset_id, role)
                if not success:
                    raise BusinessException(PARAM_ERROR, "资产关联不存在")
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

        return {
            "product_id": product_id,
            "removed_asset_id": asset_id,
            "message": "资产关联删除成功"
        }

    @staticmethod
    def update_asset_role(
        db: Session,
        product_id: int,
        asset_id: int,
        user_id: int,
        new_role: str
    ) -> dict:
        """修改商品关联资产的角色

        :param db: 数据库会话
        :param product_id: 商品ID
        :param asset_id: 资产ID
        :param user_id: 当前用户ID
        :param new_role: 新的角色（main/image/video/audio）
        :return: 修改结果
        :raises BusinessException: 商品不存在、无权限、关联不存在时抛出
        """
        # 校验商品存在且用户有权限
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 校验资产存在且属于当前用户
        asset = AssetDAO.get_asset_by_id(db, asset_id)
        if not asset:
            raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 不存在")
        if asset.user_id != user_id:
            raise BusinessException(FORBIDDEN, f"无权限操作资产ID {asset_id}")

        # 校验角色合法性
        allowed_roles = {"main", "image", "video", "audio"}
        if new_role not in allowed_roles:
            raise BusinessException(PARAM_ERROR, f"角色不合法，允许的角色：{', '.join(allowed_roles)}")

        try:
            # 开启事务
            with db.begin_nested():
                # 先删除旧关联
                ProductAssetDAO.delete_product_asset(db, product_id, asset_id)
                # 再创建新关联
                ProductAssetDAO.create_product_asset(db, product_id, asset_id, new_role)
            # 事务提交成功
        except Exception as e:
            # 事务回滚，重新抛出异常
            db.rollback()
            raise e

        return {
            "product_id": product_id,
            "asset_id": asset_id,
            "new_role": new_role,
            "message": "资产角色更新成功"
        }

    @staticmethod
    def list_product_assets(
        db: Session,
        product_id: int,
        user_id: int,
        role: Optional[str] = None
    ) -> List[dict]:
        """获取商品关联的资产列表

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID
        :param role: 可选，按角色筛选
        :return: 资产列表
        :raises BusinessException: 商品不存在、无权限时抛出
        """
        # 校验商品存在且用户有权限
        product = ProductDAO.get_product_by_id(db, product_id, include_assets=True)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 查询关联的资产
        if role:
            assets = ProductAssetDAO.get_assets_by_product_id_and_role(db, product_id, role)
        else:
            assets = ProductAssetDAO.get_assets_by_product_id(db, product_id)

        # 转换为字典格式
        return [asset.to_dict() for asset in assets]


# 模块级单例，Controller 层直接引用
product_service = ProductService()
