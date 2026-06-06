"""商品模块"""
from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.product.dao.product_category_dao import ProductCategoryDAO
from backend.v1.app.product.dao.product_asset_dao import ProductAssetDAO
from backend.v1.app.product.service.product_service import product_service
from backend.v1.app.product.service.product_category_service import ProductCategoryService

__all__ = [
    "ProductDAO",
    "ProductCategoryDAO",
    "ProductAssetDAO",
    "product_service",
    "ProductCategoryService"
]
