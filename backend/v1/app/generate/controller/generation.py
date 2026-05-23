"""剧本生成 & 视频生成 API 路由"""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.generation import GenerateRequest, GenerateResponse, ProjectDetail
from backend.app.schemas.project import ProjectResponse, ProjectCreate
from backend.app.services.script_generation import script_generation_service
from backend.app.services.video_generation import video_generation_service
from backend.framework.web import Response
from backend.app.exceptions import BusinessException
from backend.app.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR

router = APIRouter(prefix="/api/v1/projects", tags=["视频生成"])


@router.post("", response_model=Response)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建视频项目"""
    from backend.app.models.project import Project
    p = Project(title=project.title, description=project.description)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return Response.success(data={"id": p.id, "title": p.title})


@router.get("/{project_id}", response_model=Response)
async def get_project(project_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    """查询项目详情（含状态、剧本、素材），前端轮询用"""
    try:
        detail = await video_generation_service.get_project_detail(db, project_id)
        return Response.success(data=detail)
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")


@router.post("/{project_id}/generate", response_model=Response)
async def generate_script_and_video(
    req: GenerateRequest,
    project_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """提交剧本生成 + 视频生成任务"""
    try:
        # 1. 先生成剧本（同步）
        script = await script_generation_service.generate_script(
            db, project_id, req.target_duration
        )

        # 2. 再提交视频生成（异步）
        result = await video_generation_service.submit_generation_task(db, project_id)

        return Response.success(data={
            "project_id": result["project_id"],
            "script_id": script.id,
            "status": result["status"],
        })
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/{project_id}/regenerate-script", response_model=Response)
async def regenerate_script(
    req: GenerateRequest,
    project_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """重新生成剧本（覆盖）"""
    try:
        script = await script_generation_service.generate_script(
            db, project_id, req.target_duration
        )
        return Response.success(data={
            "project_id": project_id,
            "script_id": script.id,
            "status": "script_ready",
        })
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
