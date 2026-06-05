"""商品业务逻辑层

职责：处理商品相关的业务逻辑，包括创建、查询、更新、删除商品。
权限校验在此层完成（只有商品所有者或管理员可修改/删除）。
不直接操作数据库，通过 ProductDAO 访问数据层。
"""
from typing import Optional
from sqlalchemy.orm import Session

from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.product.dao.schema import product_to_dict, ProductCreateRequest, ProductUpdateRequest
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
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

        result = {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "category_id": product.category_id,
            "user_id": product.user_id,
            "auto_parse": product.auto_parse,
            "created_at": product.created_at.isoformat() if product.created_at else "",
            "updated_at": product.updated_at.isoformat() if product.updated_at else "",
        }

        return result

    @staticmethod
    def get_product(db: Session, product_id: int, include_category_info: bool = True) -> dict:
        """获取商品详情

        :param db: 数据库会话
        :param product_id: 商品ID
        :param include_category_info: 是否包含完整分类信息
        :return: 商品详细信息字典
        :raises BusinessException: 商品不存在时抛出 RESOURCE_NOT_FOUND
        """
        product = ProductDAO.get_product_by_id(db, product_id, include_category=include_category_info)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        return product_to_dict(product, include_category_info=include_category_info)

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
    def parse_product(db: Session, product_id: int, user_id: int, force: bool = False) -> str:
        """手动触发商品解析

        :param db: 数据库会话
        :param product_id: 商品ID
        :param user_id: 当前用户ID（用于权限校验）
        :param force: 是否强制重新解析
        :return: 解析执行ID
        :raises BusinessException: 商品不存在或无权限时抛出异常
        """
        product = ProductDAO.get_product_by_id(db, product_id)
        if not product:
            raise BusinessException(RESOURCE_NOT_FOUND, "商品不存在")
        if product.user_id is not None and product.user_id != user_id:
            raise BusinessException(FORBIDDEN, "无权限操作此商品")

        # 检查是否正在运行
        if product.parsing_status == "running" and not force:
            return product.execution_id

        # 获取商品图片和描述
        from backend.v1.app.product.dao.schema import _parse_json_field
        images = _parse_json_field(product.images, [])
        description = product.description or ""

        # 如果没有图片和描述，无法解析
        if not images and not description:
            raise BusinessException(PARAM_ERROR, "商品没有图片和描述信息，无法解析")

        # 更新状态为运行中
        ProductDAO.update_product(db, product_id, {
            "parsing_status": "running",
            "parsing_error": None
        })

        # 构造流水线输入
        # TODO: 需要关联商品对应的asset_id，这里暂时使用product_id作为asset_id（需要根据实际业务调整）
        # 或者先创建对应的asset记录
        input_data = {
            "images": images,
            "description": description,
            "product_id": product_id,
            "asset_id": product_id,  # 临时使用product_id作为asset_id，后续根据实际关联调整
            "user_id": user_id
        }

        # 执行解析流水线（新流水线自动落库到asset表）
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

        # 保存execution_id到商品表
        ProductDAO.update_product(db, product_id, {
            "execution_id": execution_id,
            "parsing_status": "completed"  # 流水线执行完成直接标记为成功
        })

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
