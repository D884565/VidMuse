"""商品路由

职责：定义商品模块的 HTTP 接口，处理请求参数解析和响应包装。
所有业务逻辑委托给 ProductService，自身不包含业务代码。
所有接口都需要登录（通过 Bearer token 认证）。
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import UNAUTHORIZED
from backend.store.database.sync_database import get_db
from backend.v1.app.product.service.product_service import product_service
from backend.v1.app.product.dao.schema import ProductCreateRequest, ProductUpdateRequest
from backend.v1.app.user.service.user_service import user_service

router = APIRouter(prefix="/products", tags=["商品模块"])


# ==================== 认证依赖 ====================

def _get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """从 Authorization 请求头解析当前登录用户的ID

    与用户模块共用同一个认证逻辑（从 JWT token 解析 user_id）。

    :param authorization: Authorization 请求头的值
    :return: 当前用户ID
    :raises BusinessException: 未携带 token 或 token 无效时抛出 UNAUTHORIZED
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessException(UNAUTHORIZED)
    token = authorization[7:]
    return user_service.get_user_id_from_token(token)


# ==================== 商品接口 ====================

@router.post("", response_model=Response, summary="创建商品")
def create_product(
    req: ProductCreateRequest,
    current_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """添加商品信息到系统"""
    result = product_service.create_product(db, current_user_id, req)
    return Response.success(data=result, message="商品创建成功")


@router.get("", response_model=Response, summary="获取商品列表")
def list_products(
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
    current_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取商品列表，返回自己的商品 + 平台公共商品
    支持按三级分类筛选：
    - category1: 一级分类ID
    - category2: 二级分类ID
    - category3: 三级分类ID
    """
    result = product_service.list_products(
        db, user_id=current_user_id, keyword=keyword, category=category,
        category1=category1, category2=category2, category3=category3,
        platform=platform, min_price=min_price, max_price=max_price,
        only_public=only_public, page=page, page_size=page_size,
    )
    return Response.success(data=result)


@router.get("/{product_id}", response_model=Response, summary="获取商品详情")
def get_product(
    product_id: int,
    current_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取商品详细信息，包括卖点、规格、标签等"""
    result = product_service.get_product(db, product_id)
    return Response.success(data=result)


@router.put("/{product_id}", response_model=Response, summary="更新商品")
def update_product(
    product_id: int,
    req: ProductUpdateRequest,
    current_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """更新商品信息（仅商品所有者可操作）"""
    result = product_service.update_product(db, product_id, current_user_id, req)
    return Response.success(data=result, message="商品更新成功")


@router.delete("/{product_id}", response_model=Response, summary="删除商品")
def delete_product(
    product_id: int,
    current_user_id: int = Depends(_get_current_user_id),
    db: Session = Depends(get_db),
):
    """删除商品（仅商品所有者可操作）"""
    product_service.delete_product(db, product_id, current_user_id)
    return Response.success(data=None, message="商品删除成功")
