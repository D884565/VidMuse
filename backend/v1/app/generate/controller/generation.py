"""剧本生成 & 视频生成 API 路由"""
import json
import logging

from typing import Optional

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.generate.dao.project import ProjectCreate
from backend.v1.app.generate.service.project_service import ProjectService
from backend.v1.app.generate.service.script_generation import script_generation_service
from backend.v1.app.generate.service.video_generation import video_generation_service
from backend.v1.app.generate.service.chat_service import chat_service
from backend.v1.app.generate.service.task_service import generation_task_service
from backend.v1.app.product.service.product_crawl_service import product_crawl_service
from backend.framework.web import Response
from backend.framework.web.auth import get_current_user_id
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR, UNAUTHORIZED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate/v1", tags=["视频生成"])

SCRIPT_BLOCKED_STATUSES = {"script_generating", "render_queued", "rendering", "processing"}


@router.post("/projects", response_model=Response)
async def create_project(
    project: ProjectCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建视频项目。默认只保存项目；auto_render=true 时保留一键成片体验。"""
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
        user_id=current_user_id,
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

    response_data = {
        "id": p.id,
        "project_id": p.id,
        "title": p.title,
        "product_info_crawled": product_info_str is not None,
        "status": p.status,
    }

    if project.auto_render:
        script_task = None
        try:
            script_task = await generation_task_service.create_task(db, p.id, "script", status="running")
            p.status = "script_generating"
            await db.commit()

            frames = await script_generation_service.generate_script(db, p.id)
            from datetime import datetime
            script_task.status = "succeeded"
            script_task.progress = 100
            script_task.current_step = "SCRIPT_GENERATED"
            script_task.finished_at = datetime.utcnow()
            await db.commit()

            result = await video_generation_service.submit_generation_task(db, p.id)
            logger.info(f"[项目创建] 自动触发生成成功: project_id={p.id}")
            response_data.update({
                "task_id": result.get("task_id"),
                "script_task_id": script_task.id,
                "frames_count": len(frames),
                "status": result.get("status", "render_queued"),
            })
        except Exception as e:
            logger.warning(f"[项目创建] 自动触发生成失败: {e}")
            p.status = "failed"
            if script_task:
                from datetime import datetime
                script_task.status = "failed"
                script_task.progress = 100
                script_task.error_message = str(e)
                script_task.finished_at = datetime.utcnow()
                await db.commit()
            await db.refresh(p)
            response_data.update({"status": p.status, "generate_error": str(e)})

    return Response.success(data=response_data)


@router.get("/projects", response_model=Response)
async def list_projects(
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """项目列表（分页，仅返回当前用户的项目）"""
    result = await ProjectService.list_projects(
        db=db, user_id=current_user_id, status=status, keyword=keyword, page=page, page_size=page_size
    )
    return Response.success(data=result)


@router.get("/projects/{project_id}", response_model=Response)
async def get_project(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询项目详情（含状态、帧、素材），前端轮询用"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")
    try:
        detail = await video_generation_service.get_project_detail(db, project_id)
        return Response.success(data=detail)
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")


@router.put("/projects/{project_id}", response_model=Response)
async def update_project(
    update_data: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新项目信息"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权修改该项目")
    try:
        result = await ProjectService.update_project(db, project_id, update_data)
        return Response.success(data=result)
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(RESOURCE_NOT_FOUND, f"更新失败: {e}")


@router.delete("/projects/{project_id}", response_model=Response)
async def delete_project(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除项目"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权删除该项目")
    try:
        await ProjectService.delete_project(db, project_id)
        return Response.success(data={"deleted": True})
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(RESOURCE_NOT_FOUND, f"删除失败: {e}")


@router.post("/projects/{project_id}/script/generate", response_model=Response)
async def generate_project_script(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """独立生成项目剧本。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    from backend.v1.app.models.project import Project

    status_result = await db.execute(select(Project.status).where(Project.id == project_id))
    current_status = status_result.scalar_one()
    if current_status in SCRIPT_BLOCKED_STATUSES:
        raise BusinessException(VIDEO_ERROR, f"当前状态不允许重新生成剧本: {current_status}")

    task = await generation_task_service.create_task(db, project_id, "script", status="running")
    try:
        from datetime import datetime

        result = await db.execute(select(Project).where(Project.id == project_id))
        project_model = result.scalar_one()
        project_model.status = "script_generating"
        await db.commit()

        frames = await script_generation_service.generate_script(db, project_id)
        task.status = "succeeded"
        task.progress = 100
        task.current_step = "SCRIPT_GENERATED"
        task.finished_at = datetime.utcnow()
        await db.commit()

        return Response.success(data={
            "task_id": task.id,
            "project_id": project_id,
            "frames_count": len(frames),
            "status": "script_ready",
        })
    except Exception as e:
        from datetime import datetime
        result = await db.execute(select(Project).where(Project.id == project_id))
        project_model = result.scalar_one_or_none()
        if project_model:
            project_model.status = "failed"
        task.status = "failed"
        task.progress = 100
        task.error_message = str(e)
        task.finished_at = datetime.utcnow()
        await db.commit()
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/projects/{project_id}/render", response_model=Response)
async def render_project(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """提交项目渲染任务。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    try:
        result = await video_generation_service.submit_generation_task(db, project_id)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.get("/tasks/{task_id}", response_model=Response)
async def get_generation_task(
    task_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询生成任务状态。"""
    try:
        result = await generation_task_service.get_task(db, task_id, current_user_id)
        return Response.success(data=result)
    except PermissionError:
        raise BusinessException(UNAUTHORIZED, "无权访问该任务")
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"任务不存在: {task_id}")


@router.get("/tasks/{task_id}/steps", response_model=Response)
async def get_generation_task_steps(
    task_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询生成任务步骤。"""
    try:
        result = await generation_task_service.list_steps(db, task_id, current_user_id)
        return Response.success(data=result)
    except PermissionError:
        raise BusinessException(UNAUTHORIZED, "无权访问该任务")
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"任务不存在: {task_id}")


@router.post("/projects/{project_id}/chat", response_model=Response)
async def chat_refinement(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """对话式调整：用户发送指令，系统重新生成受影响的部分"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    try:
        content = req.get("content", "")
        frame_id = req.get("frame_id")
        if not content:
            raise BusinessException(VIDEO_ERROR, "content 不能为空")
        result = await chat_service.handle_message(db, project_id, content, frame_id)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.get("/projects/{project_id}/conversations", response_model=Response)
async def get_conversations(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取项目对话历史"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")
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


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate", response_model=Response)
async def regenerate_frame(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """重新生成指定帧的脚本+图片"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    try:
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame(db, project_id, frame_id, instruction)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate-image", response_model=Response)
async def regenerate_frame_image(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """只重新生成指定帧的图片（脚本不变）"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    try:
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame_image(db, project_id, frame_id, instruction)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/projects/{project_id}/frames/{frame_id}/retry", response_model=Response)
async def retry_frame(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """重试失败分镜并提交整片重新渲染。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")

    from sqlalchemy import select
    from backend.v1.app.models.frame import Frame

    result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
    frame = result.scalar_one_or_none()
    if not frame:
        raise BusinessException(RESOURCE_NOT_FOUND, f"分镜不存在: {frame_id}")
    if frame.status != 3:
        raise BusinessException(VIDEO_ERROR, "只能重试失败的分镜")

    instruction = (req or {}).get("instruction")
    if instruction:
        frame.description = f"{frame.description or ''}\n\n用户重试要求：{instruction}"
    frame.status = 0
    frame.error_message = None
    await db.commit()

    render_result = await video_generation_service.submit_generation_task(db, project_id)
    return Response.success(data={
        "frame_id": frame_id,
        "project_id": project_id,
        "task_id": render_result.get("task_id"),
        "status": render_result.get("status"),
    })
