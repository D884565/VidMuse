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
