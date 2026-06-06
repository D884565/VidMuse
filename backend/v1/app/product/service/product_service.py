"""商品业务逻辑层

职责：处理商品相关的业务逻辑，包括创建、查询、更新、删除商品。
权限校验在此层完成（只有商品所有者或管理员可修改/删除）。
不直接操作数据库，通过 ProductDAO 访问数据层。
"""
import json
from typing import Optional, List
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import ValidationError

from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.product.dao.product_asset_dao import ProductAssetDAO
from backend.v1.app.product.dao.schema import product_to_dict, ProductCreateRequest, ProductUpdateRequest
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.assets.service.asset_service import AssetService
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import (
    RESOURCE_NOT_FOUND,
    FORBIDDEN,
    PARAM_ERROR,
)
from backend.v1.app.pipeline.pipelines.product_parsing_pipeline import ProductParsingPipeline


class ProductService:
    """商品业务逻辑层"""

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

        product = ProductDAO.create_product(db, product_data)

        # 处理资产关联
        asset_ids = data.asset_ids
        if asset_ids:
            # 验证所有资产是否存在
            for asset_id in asset_ids:
                asset = AssetDAO.get_asset_by_id(db, asset_id)
                if not asset:
                    raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 不存在")
                # 校验资产所属权（暂时跳过，待用户系统完善后添加）

            # 批量创建关联
            ProductAssetDAO.create_product_assets_batch(
                db,
                product_id=product.id,
                asset_ids=asset_ids,
                roles=data.asset_roles
            )

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
    def get_product(db: Session, product_id: int, include_category_info: bool = True, include_assets: bool = True) -> dict:
        """获取商品详情

        :param db: 数据库会话
        :param product_id: 商品ID
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
        ProductDAO.delete_product(db, product_id)

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
        product = ProductDAO.get_product_by_id(db, product_id, include_assets=True)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 检查是否正在运行
        if product.parsing_status == "running" and not force:
            return product.execution_id

        # 获取要解析的资产
        target_asset = None
        if asset_id:
            # 指定了asset_id，查找对应的关联资产
            for asset in product.assets:
                if asset.id == asset_id:
                    target_asset = asset
                    break
            if not target_asset:
                raise BusinessException(PARAM_ERROR, f"资产ID {asset_id} 未关联到此商品")
        else:
            # 未指定asset_id，优先找角色为main的资产，否则取第一个
            main_assets = ProductAssetDAO.get_assets_by_product_id_and_role(db, product_id, "main")
            if main_assets:
                target_asset = main_assets[0]
            elif product.assets:
                target_asset = product.assets[0]

        # 获取商品图片和描述（兼容旧版数据）
        from backend.v1.app.product.dao.schema import _parse_json_field
        images = _parse_json_field(product.images, [])
        description = product.description or ""

        # 如果有目标资产，使用资产的内容进行解析
        if target_asset:
            # 如果是图片类型，添加到images列表
            if target_asset.type == 1:  # 图片
                images = [target_asset.url] + images
            # 如果是视频或音频，优先使用资产内容
            elif target_asset.type in [2, 3]:  # 视频/音频
                input_data = {
                    "asset_id": target_asset.id,
                    "asset_type": target_asset.type,
                    "asset_url": target_asset.url,
                    "product_id": product_id,
                    "user_id": user_id,
                    "description": description
                }
        else:
            # 没有关联资产，使用旧版的images和description字段
            if not images and not description:
                raise BusinessException(PARAM_ERROR, "商品没有关联资产和描述信息，无法解析")

            input_data = {
                "images": images,
                "description": description,
                "product_id": product_id,
                "user_id": user_id
            }

        # 更新状态为运行中
        ProductDAO.update_product(db, product_id, {
            "parsing_status": "running",
            "parsing_error": None
        })

        # 执行解析流水线
        pipeline = ProductParsingPipeline(
            persist_to_asset=True,  # 自动落库到asset表
            enable_persistence=True
        )
        result = pipeline.run_with_persistence(input_data)

        if not result["success"]:
            error_msg = f"解析任务启动失败: {result['errors'][0] if result['errors'] else '未知错误'}"
            ProductDAO.update_product(db, product_id, {
                "parsing_status": "failed",
                "parsing_error": error_msg
            })
            raise BusinessException(PARAM_ERROR, error_msg)

        execution_id = result["execution_id"]

        # 从解析结果中提取描述，回写到商品表（仅当商品描述为空时）
        update_fields = {
            "execution_id": execution_id,
            "parsing_status": "completed",
        }
        if not product.description:
            product_data = (result.get("data") or {}).get("product_data", {})
            generated_desc = (product_data.get("basic_info") or {}).get("description", "")
            if generated_desc and isinstance(generated_desc, str) and generated_desc.strip():
                update_fields["description"] = generated_desc.strip()

        ProductDAO.update_product(db, product_id, update_fields)

        return execution_id

    @staticmethod
    def get_parsing_progress(db: Session, product_id: int, user_id: int) -> dict:
        """
        查询商品解析进度
        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID
        :return: 进度信息
        """
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 基础信息
        progress = {
            "product_id": product.id,
            "parsing_status": product.parsing_status,
            "execution_id": product.execution_id,
            "parsing_error": product.parsing_error,
            "ai_features": product.ai_features,
            "description": product.description,
            "updated_at": product.updated_at.isoformat() + "Z" if product.updated_at else None
        }

        # 如果有execution_id，查询详细进度
        if product.execution_id:
            from backend.v1.app.pipeline import ProductParsingPipeline
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
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 检查状态
        if product.parsing_status not in ["failed", None]:
            raise BusinessException(PARAM_ERROR, "只有失败的解析任务可以重试")

        # 如果有execution_id，尝试断点恢复
        if product.execution_id:
            try:
                from backend.v1.app.pipeline import ProductParsingPipeline
                pipeline = ProductParsingPipeline()

                # 更新状态为运行中
                ProductDAO.update_product(db, product_id, {
                    "parsing_status": "running",
                    "parsing_error": None
                })

                # 恢复执行
                result = pipeline.resume_execution(product.execution_id)

                if result["success"]:
                    # 新流水线自动落库到asset表，直接更新状态为完成
                    ProductDAO.update_product(db, product_id, {
                        "parsing_status": "completed"
                    })
                    return product.execution_id  # type: ignore
                else:
                    # 重试失败
                    error_msg = f"重试解析失败: {result['errors'][0] if result['errors'] else '未知错误'}"
                    ProductDAO.update_product(db, product_id, {
                        "parsing_status": "failed",
                        "parsing_error": error_msg
                    })
                    raise BusinessException(PARAM_ERROR, error_msg)

            except Exception as e:
                # 恢复失败，降级为重新执行
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"断点恢复失败，将重新执行完整解析: {str(e)}")

        # 没有execution_id或恢复失败，重新执行完整解析
        return ProductService.parse_product(db, product_id, user_id, force=True)

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
                skip_analysis=True  # 跳过自动解析，由商品解析统一处理
            )
            asset_ids.append(asset_result["id"])
            # 设置资产角色
            role = asset_roles.get(index, "main" if index == 0 else "image") if asset_roles else ("main" if index == 0 else "image")
            asset_role_map[asset_result["id"]] = role

        # 2. 创建商品并关联资产
        req.asset_ids = asset_ids
        req.asset_roles = asset_role_map
        product_result = ProductService.create_product(db, user_id, req)

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


# 模块级单例，Controller 层直接引用
product_service = ProductService()
