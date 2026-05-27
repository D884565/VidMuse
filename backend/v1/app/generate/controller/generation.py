"""剧本生成 & 视频生成 API 路由"""
import json
import logging

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.generate.dao.project import ProjectCreate
from backend.v1.app.generate.service.script_generation import script_generation_service
from backend.v1.app.generate.service.video_generation import video_generation_service
from backend.v1.app.generate.service.chat_service import chat_service
from backend.v1.app.product.service.product_crawl_service import product_crawl_service
from backend.framework.web import Response
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate/v1/projects", tags=["视频生成"])


@router.post("", response_model=Response)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建视频项目，自动触发剧本+视频生成"""
    from backend.v1.app.models.project import Project

    product_info_str = None

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
        target_duration=project.target_duration,
        voice_type=project.voice_type,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)

    try:
        await script_generation_service.generate_script(db, p.id)
        result = await video_generation_service.submit_generation_task(db, p.id)
        logger.info(f"[项目创建] 自动触发生成成功: project_id={p.id}")
        return Response.success(data={
            "id": p.id,
            "title": p.title,
            "product_info_crawled": product_info_str is not None,
            "frames_count": result.get("frames_count"),
            "status": result.get("status", "processing"),
        })
    except Exception as e:
        logger.warning(f"[项目创建] 自动触发生成失败: {e}")
        return Response.success(data={
            "id": p.id,
            "title": p.title,
            "product_info_crawled": product_info_str is not None,
            "status": "draft",
            "generate_error": str(e),
        })


@router.get("/{project_id}", response_model=Response)
async def get_project(project_id: int = Path(..., gt=0), db: AsyncSession = Depends(get_db)):
    """查询项目详情（含状态、帧、素材），前端轮询用"""
    try:
        detail = await video_generation_service.get_project_detail(db, project_id)
        return Response.success(data=detail)
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")


@router.post("/{project_id}/chat", response_model=Response)
async def chat_refinement(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """对话式调整：用户发送指令，系统重新生成受影响的部分"""
    try:
        content = req.get("content", "")
        frame_id = req.get("frame_id")
        if not content:
            raise BusinessException(VIDEO_ERROR, "content 不能为空")
        result = await chat_service.handle_message(db, project_id, content, frame_id)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.get("/{project_id}/conversations", response_model=Response)
async def get_conversations(
    project_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """获取项目对话历史"""
    from sqlalchemy import select
    from backend.v1.app.models.conversation import Conversation

    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.created_at.asc())
    )
    conversations = result.scalars().all()
    return Response.success(data=[
        {
            "id": c.id,
            "role": c.role,
            "content": c.content,
            "frame_id": c.frame_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in conversations
    ])


@router.post("/{project_id}/frames/{frame_id}/regenerate", response_model=Response)
async def regenerate_frame(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """重新生成指定帧的脚本+图片"""
    try:
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame(db, project_id, frame_id, instruction)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/{project_id}/frames/{frame_id}/regenerate-image", response_model=Response)
async def regenerate_frame_image(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """只重新生成指定帧的图片（脚本不变）"""
    try:
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame_image(db, project_id, frame_id, instruction)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
