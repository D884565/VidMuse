"""商品分类路由

职责：定义商品分类模块的 HTTP 接口，处理请求参数解析和响应包装。
所有业务逻辑委托给 ProductCategoryService，自身不包含业务代码。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.framework.web.response import Response
from backend.framework.exceptions.exceptions import BusinessException
from backend.store.database.sync_database import get_db
from backend.v1.app.product.dao.schema import CategoryCreateRequest, CategoryUpdateRequest
from backend.v1.app.product.service.product_category_service import ProductCategoryService
from backend.framework.web.auth import admin_required  # 管理员权限校验

router = APIRouter(prefix="/product/categories", tags=["商品分类模块"])


# ==================== 分类接口 ====================

@router.get("/tree", response_model=Response, summary="获取分类树")
def get_category_tree(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """获取完整的三级分类树结构"""
    result = ProductCategoryService.get_category_tree(db)
    return Response.success(data=result)


@router.get("/level/{level}", response_model=Response, summary="按层级查询分类")
def get_categories_by_level(
    level: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """按层级查询分类列表，level=1为一级分类，level=2为二级，level=3为三级"""
    try:
        result = ProductCategoryService.get_categories_by_level(db, level)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(str(e))


@router.get("/{category_id}", response_model=Response, summary="获取分类详情")
def get_category_info(
    category_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """根据分类ID获取分类详细信息"""
    result = ProductCategoryService.get_category_info(db, category_id)
    if not result:
        raise BusinessException("分类不存在")
    return Response.success(data=result)


@router.post("", response_model=Response, summary="创建分类")
def create_category(
    req: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """创建新的分类，最多支持三级分类"""
    try:
        result = ProductCategoryService.create_category(db, req)
        return Response.success(data=result, message="分类创建成功")
    except ValueError as e:
        raise BusinessException(str(e))


@router.put("/{category_id}", response_model=Response, summary="更新分类")
def update_category(
    category_id: int,
    req: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """更新分类信息，支持修改名称、父分类、排序等"""
    try:
        result = ProductCategoryService.update_category(db, category_id, req)
        return Response.success(data=result, message="分类更新成功")
    except ValueError as e:
        raise BusinessException(str(e))


@router.delete("/{category_id}", response_model=Response, summary="删除分类")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    """删除分类（软删除），有子分类的分类不能删除"""
    try:
        success = ProductCategoryService.delete_category(db, category_id)
        if success:
            return Response.success(data=None, message="分类删除成功")
        raise BusinessException("分类删除失败")
    except ValueError as e:
        raise BusinessException(str(e))
