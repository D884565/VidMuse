"""灵感模板路由

职责：定义灵感模板模块的 HTTP 接口，处理请求参数解析和响应包装。
所有业务逻辑委托给对应的 Service，自身不包含业务代码。
"""
from typing import Optional
from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.framework.web.response import Response
from backend.framework.web.auth import admin_required
from backend.store.database.async_database import get_db
from backend.v1.app.admin.inspiration_template.service.inspiration_service import (
    factor_service,
    strategy_service,
    inspiration_template_service,
    template_factor_relation_service
)
from backend.v1.app.admin.inspiration_template.dao.schema import (
    # 因子相关
    FactorCreateRequest,
    FactorUpdateRequest,
    FactorResponse,
    # 策略相关
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
    # 模板相关
    InspirationTemplateCreateRequest,
    InspirationTemplateUpdateRequest,
    InspirationTemplateResponse,
    # 关联相关
    TemplateFactorRelationCreateRequest,
    TemplateFactorRelationUpdateRequest,
    TemplateFactorRelationResponse,
)

router = APIRouter(
    prefix="/admin/inspiration",
    tags=["后台-灵感模板模块"],
    dependencies=[Depends(admin_required)]  # 所有接口强制管理员权限
)


# ==================== 创作因子接口 ====================

@router.post("/factors", response_model=Response[FactorResponse], summary="创建创作因子")
async def create_factor(req: FactorCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建新的创作因子"""
    result = await factor_service.create_factor(db, req.model_dump())
    return Response.success(data=result, message="创建成功")


@router.get("/factors/{factor_id}", response_model=Response[FactorResponse], summary="获取因子详情")
async def get_factor(factor_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取因子详细信息"""
    result = await factor_service.get_factor(db, factor_id)
    return Response.success(data=result)


@router.put("/factors/{factor_id}", response_model=Response[FactorResponse], summary="更新因子信息")
async def update_factor(factor_id: int, req: FactorUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新因子的信息"""
    result = await factor_service.update_factor(db, factor_id, req.model_dump(exclude_unset=True))
    return Response.success(data=result, message="更新成功")


@router.delete("/factors/{factor_id}", response_model=Response, summary="删除因子")
async def delete_factor(factor_id: int, db: AsyncSession = Depends(get_db)):
    """删除指定因子（软删除）"""
    await factor_service.delete_factor(db, factor_id)
    return Response.success(message="删除成功")


@router.get("/factors", response_model=Response, summary="分页查询因子列表")
async def list_factors(
    factor_type: Optional[str] = Query(None, description="按因子类型筛选：content_structure/product_expression/user_operation"),
    keyword: Optional[str] = Query(None, description="按名称/描述模糊搜索"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """分页查询创作因子列表，支持多种筛选条件"""
    result = await factor_service.list_factors(
        db, factor_type=factor_type, keyword=keyword, tag=tag, page=page, page_size=page_size
    )
    return Response.success(data=result)


# ==================== 创作策略接口 ====================

@router.post("/strategies", response_model=Response[StrategyResponse], summary="创建创作策略")
async def create_strategy(req: StrategyCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建新的创作策略"""
    result = await strategy_service.create_strategy(db, req.model_dump())
    return Response.success(data=result, message="创建成功")


@router.get("/strategies/{strategy_id}", response_model=Response[StrategyResponse], summary="获取策略详情")
async def get_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取策略详细信息"""
    result = await strategy_service.get_strategy(db, strategy_id)
    return Response.success(data=result)


@router.put("/strategies/{strategy_id}", response_model=Response[StrategyResponse], summary="更新策略信息")
async def update_strategy(strategy_id: int, req: StrategyUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新策略的信息"""
    result = await strategy_service.update_strategy(db, strategy_id, req.model_dump(exclude_unset=True))
    return Response.success(data=result, message="更新成功")


@router.delete("/strategies/{strategy_id}", response_model=Response, summary="删除策略")
async def delete_strategy(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """删除指定策略（软删除）"""
    await strategy_service.delete_strategy(db, strategy_id)
    return Response.success(message="删除成功")


@router.get("/strategies", response_model=Response, summary="分页查询策略列表")
async def list_strategies(
    applicable_scenario: Optional[str] = Query(None, description="按适用场景筛选"),
    keyword: Optional[str] = Query(None, description="按名称/描述模糊搜索"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    min_success_rate: Optional[float] = Query(None, ge=0, le=1, description="最低成功率筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """分页查询创作策略列表，支持多种筛选条件"""
    result = await strategy_service.list_strategies(
        db, applicable_scenario=applicable_scenario, keyword=keyword, tag=tag,
        min_success_rate=min_success_rate, page=page, page_size=page_size
    )
    return Response.success(data=result)


# ==================== 灵感模板接口 ====================

@router.post("/templates", response_model=Response[InspirationTemplateResponse], summary="创建灵感模板")
async def create_template(req: InspirationTemplateCreateRequest, db: AsyncSession = Depends(get_db)):
    """创建新的灵感模板，支持同时关联因子"""
    result = await inspiration_template_service.create_template(db, req.model_dump())
    return Response.success(data=result, message="创建成功")


@router.get("/templates/{template_id}", response_model=Response[InspirationTemplateResponse], summary="获取模板详情")
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """根据ID获取模板详细信息，包含关联的策略和因子"""
    result = await inspiration_template_service.get_template_detail(db, template_id)
    return Response.success(data=result)


@router.put("/templates/{template_id}", response_model=Response[InspirationTemplateResponse], summary="更新模板信息")
async def update_template(template_id: int, req: InspirationTemplateUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新模板的信息，支持全量更新关联因子"""
    result = await inspiration_template_service.update_template(db, template_id, req.model_dump(exclude_unset=True))
    return Response.success(data=result, message="更新成功")


@router.delete("/templates/{template_id}", response_model=Response, summary="删除模板")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """删除指定模板（软删除），同时删除关联的因子关系"""
    await inspiration_template_service.delete_template(db, template_id)
    return Response.success(message="删除成功")


@router.get("/templates", response_model=Response, summary="分页查询模板列表")
async def list_templates(
    strategy_id: Optional[str] = Query(None, description="按关联策略ID筛选"),
    keyword: Optional[str] = Query(None, description="按名称/描述模糊搜索"),
    version: Optional[str] = Query(None, description="按版本号筛选"),
    min_success_rate: Optional[float] = Query(None, ge=0, le=1, description="最低成功率筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """分页查询灵感模板列表，支持多种筛选条件"""
    result = await inspiration_template_service.list_templates(
        db, strategy_id=strategy_id, keyword=keyword, version=version,
        min_success_rate=min_success_rate, page=page, page_size=page_size
    )
    return Response.success(data=result)


# ==================== 模板-因子关联接口 ====================

@router.post("/relations", response_model=Response[TemplateFactorRelationResponse], summary="添加模板-因子关联")
async def add_relation(req: TemplateFactorRelationCreateRequest, db: AsyncSession = Depends(get_db)):
    """为模板添加关联的因子"""
    result = await template_factor_relation_service.add_relation(db, req.model_dump())
    return Response.success(data=result, message="关联成功")


@router.put("/relations/{relation_id}", response_model=Response[TemplateFactorRelationResponse], summary="更新关联信息")
async def update_relation(relation_id: int, req: TemplateFactorRelationUpdateRequest, db: AsyncSession = Depends(get_db)):
    """更新关联的使用类型和排序权重"""
    result = await template_factor_relation_service.update_relation(db, relation_id, req.model_dump(exclude_unset=True))
    return Response.success(data=result, message="更新成功")


@router.delete("/relations/{relation_id}", response_model=Response, summary="删除关联")
async def delete_relation(relation_id: int, db: AsyncSession = Depends(get_db)):
    """删除模板与因子的关联关系"""
    await template_factor_relation_service.delete_relation(db, relation_id)
    return Response.success(message="删除成功")


@router.get("/templates/{template_id}/factors", response_model=Response, summary="获取模板关联的所有因子")
async def get_template_factors(template_id: str, db: AsyncSession = Depends(get_db)):
    """获取指定模板关联的所有因子，区分为必填和可选"""
    result = await template_factor_relation_service.get_template_factors(db, template_id)
    return Response.success(data=result)
