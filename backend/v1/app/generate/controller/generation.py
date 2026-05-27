"""剧本生成 & 视频生成 API 路由"""
import json
import logging

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.generate.dao.generation import GenerateRequest
from backend.v1.app.generate.dao.project import ProjectCreate
from backend.v1.app.generate.service.script_generation import script_generation_service
from backend.v1.app.generate.service.video_generation import video_generation_service
from backend.v1.app.product.service.product_crawl_service import product_crawl_service
from backend.framework.web import Response
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate/v1/projects", tags=["视频生成"])


@router.post("", response_model=Response)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建视频项目，可选抓取商品信息"""
    from backend.v1.app.models.project import Project

    product_info_str = None

    # 如果提供了商品URL，尝试抓取商品信息
    if project.product_url:
        try:
            product_info = await product_crawl_service.crawl(project.product_url)
            if not product_info.is_empty:
                product_info_str = json.dumps(product_info.to_dict(), ensure_ascii=False)
                logger.info(f"[项目创建] 商品抓取成功: {product_info.title}")
        except Exception as e:
            logger.warning(f"[项目创建] 商品抓取失败，继续创建项目: {e}")

    p = Project(
        title=project.title,
        description=project.description,
        product_url=project.product_url,
        product_info=product_info_str,
        user_prompt=project.user_prompt,
        reference_images=project.reference_images or [],
        style=project.style,
        target_audience=project.target_audience,
        key_points=project.key_points or [],
        avoid=project.avoid or [],
        rag_weight=project.rag_weight,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)

    return Response.success(data={
        "id": p.id,
        "title": p.title,
        "product_info_crawled": product_info_str is not None,
    })


@router.get("/{project_id}", response_model=Response)
async def get_project(project_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    """查询项目详情（含状态、帧、素材），前端轮询用"""
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
        # 1. 先生成剧本（写入 frames 表）
        await script_generation_service.generate_script(
            db, project_id, req.target_duration
        )

        # 2. 再提交视频生成（异步）
        result = await video_generation_service.submit_generation_task(db, project_id)

        return Response.success(data={
            "project_id": result["project_id"],
            "frames_count": result["frames_count"],
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
    """重新生成剧本（覆盖 frames 表）"""
    try:
        frames = await script_generation_service.generate_script(
            db, project_id, req.target_duration
        )
        return Response.success(data={
            "project_id": project_id,
            "frames_count": len(frames),
            "status": "script_ready",
        })
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
