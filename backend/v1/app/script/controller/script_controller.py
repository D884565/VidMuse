"""剧本相关API路由"""
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.framework.web import Response
from backend.framework.web.auth import get_current_user_id
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND
from backend.v1.app.script.service.script_generation_service import script_generation_service
from backend.v1.app.script.service.inspiration_template_query_service import inspiration_template_query_service
from backend.v1.app.generate.service.generateUtils.project import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/script/v1", tags=["剧本管理"])


@router.post("/generate", response_model=Response)
async def generate_script(
    project_id: int = Body(..., description="项目ID", embed=True),
    force: bool = Body(False, description="是否强制重新生成"),
    template_id: Optional[str] = Body(None, description="使用的灵感模板ID"),
    template_params: Optional[dict] = Body(None, description="模板自定义参数"),
    creation_mode: Optional[str] = Body(None, description="创作模式：auto（自动选择）/hot_video（爆款融合）/template（模板生成）/strategy（策略因子）"),
    strategy_id: Optional[str] = Body(None, description="指定使用的创作策略ID，仅在strategy模式下有效"),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """生成剧本"""
    # 验证项目权限
    project = await ProjectService.get_project(db, project_id, current_user_id)
    if not project:
        raise BusinessException(RESOURCE_NOT_FOUND, "项目不存在")

    # 生成剧本
    frames = await script_generation_service.generate_script(
        db,
        project_id=project_id,
        force=force,
        template_id=template_id,
        template_params=template_params,
        creation_mode=creation_mode,
        strategy_id=strategy_id
    )

    return Response.success({
        "frames": frames,
        "frame_count": len(frames)
    })


@router.get("/template/list", response_model=Response)
async def list_templates(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    strategy_id: Optional[str] = Query(None, description="策略ID筛选"),
    min_success_rate: Optional[float] = Query(None, description="最低成功率筛选"),
    db: AsyncSession = Depends(get_db),
):
    """获取灵感模板列表"""
    from backend.v1.app.admin.inspiration_template.service.inspiration_service import inspiration_template_service

    result = inspiration_template_service.list_templates(
        db.sync_session,
        keyword=keyword,
        strategy_id=strategy_id,
        min_success_rate=min_success_rate,
        page=page,
        page_size=page_size
    )

    return Response.success(result)


@router.get("/template/detail", response_model=Response)
async def get_template_detail(
    template_id: int = Query(..., description="模板主键ID"),
    db: AsyncSession = Depends(get_db),
):
    """获取模板详细信息"""
    from backend.v1.app.admin.inspiration_template.service.inspiration_service import inspiration_template_service

    template = inspiration_template_service.get_template_detail(db.sync_session, template_id)
    return Response.success(template)


# ===================== 灵感模板查询相关接口 =====================

@router.get("/inspiration/template/list", response_model=Response)
async def list_inspiration_templates(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索（名称/描述）"),
    strategy_id: Optional[str] = Query(None, description="按策略ID筛选"),
    version: Optional[str] = Query(None, description="按版本号筛选"),
    min_success_rate: Optional[float] = Query(None, description="最低成功率筛选（0-1）", ge=0, le=1),
    include_basic_info: bool = Query(False, description="是否包含额外基础信息（策略名称、因子数量）"),
    db: AsyncSession = Depends(get_db),
):
    """分页查询灵感模板列表"""
    total, templates = await inspiration_template_query_service.list_templates(
        db=db,
        strategy_id=strategy_id,
        keyword=keyword,
        version=version,
        min_success_rate=min_success_rate,
        page=page,
        page_size=page_size,
        include_basic_info=include_basic_info
    )

    return Response.success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": templates
    })


@router.get("/inspiration/template/detail", response_model=Response)
async def get_inspiration_template_detail(
    template_id: str = Query(..., description="模板全局唯一ID"),
    include_strategy: bool = Query(True, description="是否包含关联策略信息"),
    include_factors: bool = Query(True, description="是否包含关联因子信息"),
    db: AsyncSession = Depends(get_db),
):
    """获取灵感模板详情"""
    template = await inspiration_template_query_service.get_template_detail(
        db=db,
        template_id=template_id,
        include_strategy=include_strategy,
        include_factors=include_factors
    )

    if not template:
        raise BusinessException(RESOURCE_NOT_FOUND, "模板不存在")

    return Response.success(template)


@router.get("/inspiration/strategy/list", response_model=Response)
async def list_inspiration_strategies(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索（名称/描述）"),
    applicable_scenario: Optional[str] = Query(None, description="按适用场景筛选"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    min_success_rate: Optional[float] = Query(None, description="最低成功率筛选（0-1）", ge=0, le=1),
    db: AsyncSession = Depends(get_db),
):
    """分页查询创作策略列表"""
    total, strategies = await inspiration_template_query_service.list_strategies(
        db=db,
        applicable_scenario=applicable_scenario,
        keyword=keyword,
        tag=tag,
        min_success_rate=min_success_rate,
        page=page,
        page_size=page_size
    )

    return Response.success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": strategies
    })


@router.get("/inspiration/strategy/detail", response_model=Response)
async def get_inspiration_strategy_detail(
    strategy_id: str = Query(..., description="策略全局唯一ID"),
    include_templates: bool = Query(False, description="是否包含关联模板列表"),
    template_limit: int = Query(5, description="关联模板返回数量限制", ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """获取创作策略详情"""
    strategy = await inspiration_template_query_service.get_strategy_detail(
        db=db,
        strategy_id=strategy_id,
        include_templates=include_templates,
        template_limit=template_limit
    )

    if not strategy:
        raise BusinessException(RESOURCE_NOT_FOUND, "策略不存在")

    return Response.success(strategy)


@router.get("/inspiration/factor/list", response_model=Response)
async def list_inspiration_factors(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索（名称/描述）"),
    factor_type: Optional[str] = Query(None, description="按因子类型筛选：content_structure/product_expression/user_operation"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    min_popularity: Optional[float] = Query(None, description="最低流行度筛选（0-1）", ge=0, le=1),
    db: AsyncSession = Depends(get_db),
):
    """分页查询创作因子列表"""
    total, factors = await inspiration_template_query_service.list_factors(
        db=db,
        factor_type=factor_type,
        keyword=keyword,
        tag=tag,
        min_popularity=min_popularity,
        page=page,
        page_size=page_size
    )

    return Response.success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "list": factors
    })


@router.get("/inspiration/factor/detail", response_model=Response)
async def get_inspiration_factor_detail(
    factor_id: str = Query(..., description="因子全局唯一ID"),
    include_related_templates: bool = Query(False, description="是否包含使用该因子的模板列表"),
    template_limit: int = Query(5, description="关联模板返回数量限制", ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """获取创作因子详情"""
    factor = await inspiration_template_query_service.get_factor_detail(
        db=db,
        factor_id=factor_id,
        include_related_templates=include_related_templates,
        template_limit=template_limit
    )

    if not factor:
        raise BusinessException(RESOURCE_NOT_FOUND, "因子不存在")

    return Response.success(factor)


@router.get("/inspiration/hot", response_model=Response)
async def get_inspiration_hot_recommendations(
    template_limit: int = Query(10, description="热门模板返回数量", ge=1, le=20),
    strategy_limit: int = Query(5, description="热门策略返回数量", ge=1, le=20),
    factor_limit: int = Query(10, description="热门因子返回数量", ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """获取热门推荐（模板、策略、因子）"""
    result = await inspiration_template_query_service.get_hot_recommendations(
        db=db,
        template_limit=template_limit,
        strategy_limit=strategy_limit,
        factor_limit=factor_limit
    )

    return Response.success(result)


@router.get("/inspiration/search", response_model=Response)
async def search_inspiration_all(
    keyword: str = Query(..., description="搜索关键词", min_length=1),
    limit_per_type: int = Query(10, description="每种类型返回的最大数量", ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """全局搜索灵感模板、策略、因子"""
    result = await inspiration_template_query_service.search_all(
        db=db,
        keyword=keyword,
        limit_per_type=limit_per_type
    )

    return Response.success(result)


@router.post("/revise", response_model=Response)
async def revise_script(
    project_id: int = Body(..., description="项目ID", embed=True),
    revision_instruction: str = Body(..., description="修改指令，自然语言描述需要修改的内容", embed=True),
    script_id: Optional[int] = Body(None, description="要修改的剧本ID，不传则使用项目最新激活版本"),
    current_script: Optional[Dict[str, Any]] = Body(None, description="直接传入当前剧本内容，优先级高于script_id"),
    modification_history: Optional[List[Dict[str, Any]]] = Body(None, description="历史修改记录，用于多轮修改上下文"),
    force_regenerate_frames: bool = Body(True, description="是否重新生成帧数据，默认True"),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """修改已有剧本，支持多轮协作迭代"""
    # 验证项目权限
    project = await ProjectService.get_project(db, project_id, current_user_id)
    if not project:
        raise BusinessException(RESOURCE_NOT_FOUND, "项目不存在")

    # 执行修改
    result = await script_generation_service.revise_script(
        db,
        project_id=project_id,
        revision_instruction=revision_instruction,
        script_id=script_id,
        current_script=current_script,
        modification_history=modification_history,
        force_regenerate_frames=force_regenerate_frames
    )

    return Response.success(result)
