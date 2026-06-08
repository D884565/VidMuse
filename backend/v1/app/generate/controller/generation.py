"""剧本生成 & 视频生成 API 路由"""
import json
import logging
import uuid

from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Path, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.generate.dao.project import ProjectCreate
from backend.v1.app.generate.service.generateUtils.project import ProjectService
from backend.v1.app.script.service.script_generation_service import script_generation_service
from backend.v1.app.generate.service.stages.video_workflow import video_generation_service
from backend.v1.app.generate.service.chat.chat_service import chat_service
from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message
from backend.v1.app.generate.service.chat.intent_service import intent_service
from backend.v1.app.generate.service.chat.project_title import build_video_project_title
from backend.v1.app.generate.service.chat.material_resolver import MaterialResolver
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.stages.image_workflow import image_workflow_service
from backend.v1.app.generate.service.chat.initial_message import project_initial_message_builder
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.push.service.task_event_service import task_event_service
from backend.v1.app.generate.service.generateUtils.storyboard import storyboard_service
from backend.v1.app.generate.service.workflow.blocks import build_progress_block, build_script_stage_blocks
from backend.framework.web import Response
from backend.framework.web.auth import get_current_user_id
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR, UNAUTHORIZED
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.conversation import Conversation
from backend.v1.app.models.project_asset import ProjectAsset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["视频生成"])

SCRIPT_BLOCKED_STATUSES = {"script_generating", "render_queued", "rendering", "processing"}
SCRIPT_REGENERATE_BLOCKED_STATUSES = {"script_generating", "render_queued", "rendering"}


async def _load_project_for_workflow_update(db: AsyncSession, project_id: int):
    from backend.v1.app.models.project import Project

    # 工作流推进/确认前先加行锁，尽量避免并发请求把阶段状态推进乱掉。
    result = await db.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    return result.scalar_one_or_none()


@router.post("/projects", response_model=Response)
async def create_project(
    project: ProjectCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建视频项目。默认只保存项目；auto_render=true 时保留一键成片体验。"""
    from backend.v1.app.models.conversation import Conversation
    from backend.v1.app.models.project import Project
    from backend.v1.app.models.product import Product

    product_info_str = None
    product_obj = None
    selected_assets = project.selected_assets or []

    # 如果传了 product_id，从商品表读取信息用于构建初始消息
    if project.product_id:
        product_row = await db.execute(select(Product).where(Product.id == project.product_id))
        product_obj = product_row.scalar_one_or_none()
        if product_obj:
            product_images = []
            if product_obj.images:
                try:
                    product_images = json.loads(product_obj.images) if isinstance(product_obj.images, str) else product_obj.images
                except (json.JSONDecodeError, TypeError):
                    pass
            product_info_dict = {
                "title": product_obj.name,
                "description": product_obj.description,
                "brand": product_obj.brand,
                "price": float(product_obj.price) if product_obj.price else None,
                "main_image_url": product_obj.main_image_url,
                "images": product_images,
            }
            product_info_str = json.dumps(product_info_dict, ensure_ascii=False)
    selected_asset_ids = []

    if selected_assets:
        asset_ids = []
        for item in selected_assets:
            try:
                asset_ids.append(int(item.get("id")))
            except (TypeError, ValueError, AttributeError):
                continue
        if asset_ids:
            asset_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
            assets = asset_result.scalars().all()
            resolved_materials = MaterialResolver.resolve_selected_assets(selected_assets, assets)
            selected_asset_ids = resolved_materials["selected_asset_ids"]


    # 自动生成标题和摘要：优先用商品名，否则从 user_prompt 提取
    product_name = getattr(product_obj, "name", None) if product_obj else None
    product_brand = getattr(product_obj, "brand", None) if product_obj else None

    if product_name:
        _auto_title = f"{product_brand}{product_name}带货视频" if product_brand else f"{product_name}带货视频"
    else:
        _auto_title = build_video_project_title(project.user_prompt)

    title = project.title or _auto_title
    summary = _auto_title

    p = Project(
        title=title,
        description=project.description,
        product_url=project.product_url,
        product_info=product_info_str,
        product_id=project.product_id,
        user_id=current_user_id,
        user_prompt=project.user_prompt,
        reference_images=project.reference_images,
        style=project.style,
        target_audience=project.target_audience,
        key_points=project.key_points or [],
        avoid=project.avoid or [],
        rag_weight=project.rag_weight,
        target_duration=project.target_duration,
        voice_type=project.voice_type,
        summary=summary,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)

    for asset_id in selected_asset_ids:
        db.add(ProjectAsset(project_id=p.id, asset_id=asset_id, role="reference"))
    if selected_asset_ids:
        await db.commit()

    product_info_data = None
    if product_info_str:
        try:
            product_info_data = json.loads(product_info_str)
        except (json.JSONDecodeError, TypeError):
            product_info_data = None

    # 存储系统介绍消息（assistant 角色）
    system_intro = project_initial_message_builder.build_system_intro()
    db.add(Conversation(
        project_id=p.id,
        role=system_intro["role"],
        content=system_intro["content"],
        message_type=system_intro["message_type"],
        stage=system_intro["stage"],
        blocks=system_intro["blocks"],
        metadata_=system_intro["metadata"],
    ))

    # 存储用户初始消息（user 角色）
    initial_message = project_initial_message_builder.build(
        title=p.title,
        user_prompt=p.user_prompt,
        display_user_prompt=project.display_user_prompt,
        style=p.style,
        target_audience=p.target_audience,
        key_points=p.key_points or [],
        avoid=p.avoid or [],
        target_duration=p.target_duration,
        voice_type=p.voice_type,
        product_url=p.product_url,
        reference_images=p.reference_images or [],
        product_info=product_info_data,
    )
    db.add(Conversation(
        project_id=p.id,
        role=initial_message["role"],
        content=initial_message["content"],
        message_type=initial_message["message_type"],
        stage=initial_message["stage"],
        blocks=initial_message["blocks"],
        metadata_=initial_message["metadata"],
    ))
    await db.commit()

    response_data = {
        "id": p.id,
        "project_id": p.id,
        "title": p.title,
        "product_info_crawled": product_info_str is not None,
        "status": p.status,
        "workflow_stage": p.workflow_stage,
        "stage_status": p.stage_status,
    }

    if project.auto_render:
        script_task = None
        try:
            script_task = await generation_task_service.create_task(db, p.id, "script", status="running")
            p.status = "script_generating"
            generation_workflow_service.mark_stage_running(p, "script", script_task.id)
            await db.commit()

            frames = await script_generation_service.generate_script(db, p.id)
            generation_workflow_service.mark_stage_review(p, "script", script_task.id)
            db.add(Conversation(
                project_id=p.id,
                role="assistant",
                content="剧本阶段已完成。请检查主题、风格和每个分镜内容，满意后可以确认并生成图片。",
                message_type="stage_card",
                stage="script",
                blocks=build_script_stage_blocks(frames),
                action_type="GENERATE_SCRIPT",
                task_id=script_task.id,
            ))
            from datetime import datetime
            script_task.status = "succeeded"
            script_task.progress = 100
            script_task.current_step = "SCRIPT_GENERATED"
            script_task.finished_at = datetime.utcnow()
            await db.commit()

            result = await video_generation_service.submit_generation_task(
                db,
                p.id,
                require_ready_images=False,
                trigger_source="auto_render",
            )
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
            generation_workflow_service.fail_stage(p, "script", script_task.id if script_task else None)
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
    force: bool = Query(False),
    creation_mode: str | None = Body(None, embed=True),
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
    blocked_statuses = SCRIPT_REGENERATE_BLOCKED_STATUSES if force else SCRIPT_BLOCKED_STATUSES
    if current_status in blocked_statuses:
        raise BusinessException(VIDEO_ERROR, f"当前状态不允许重新生成剧本: {current_status}")

    task = await generation_task_service.create_task(db, project_id, "script", status="running")
    try:
        from datetime import datetime

        result = await db.execute(select(Project).where(Project.id == project_id))
        project_model = result.scalar_one()
        project_model.status = "script_generating"
        generation_workflow_service.mark_stage_running(project_model, "script", task.id)
        await db.commit()

        frames = await script_generation_service.generate_script(db, project_id, force=force, creation_mode=creation_mode)
        generation_workflow_service.mark_stage_review(project_model, "script", task.id)
        from backend.v1.app.models.conversation import Conversation

        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="剧本阶段已完成。请检查主题、风格和每个分镜内容，满意后可以确认并生成图片。",
            message_type="stage_card",
            stage="script",
            blocks=build_script_stage_blocks(frames),
            action_type="GENERATE_SCRIPT",
            task_id=task.id,
        ))
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
            generation_workflow_service.fail_stage(project_model, "script", task.id)
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


@router.get("/projects/{project_id}/export/download")
async def export_project_video(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """直接下载项目成片视频，不创建异步任务、不写入素材库。"""
    from backend.v1.app.generate.service.generateUtils.export import export_service, ExportDownloadError

    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    video_url = project.get("video_output_url")
    if not video_url:
        raise BusinessException(VIDEO_ERROR, "项目还没有可导出的视频")

    try:
        stream = export_service.open_download_stream(
            video_url=video_url,
            project_title=project.get("title"),
            project_id=project_id,
        )
    except ExportDownloadError as exc:
        raise BusinessException(VIDEO_ERROR, str(exc))

    return StreamingResponse(
        stream.iter_bytes(),
        media_type=stream.media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="project_{project_id}.mp4"; '
                f"filename*=UTF-8''{quote(stream.filename)}"
            )
        },
    )


@router.post("/projects/{project_id}/assets", response_model=Response)
async def bind_project_asset(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """将用户素材绑定到当前项目，作为剧本/创作阶段可用参考素材。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")

    asset_id = req.get("asset_id")
    if not asset_id:
        raise BusinessException(VIDEO_ERROR, "asset_id 不能为空")
    asset = await db.get(Asset, asset_id)
    if not asset or asset.user_id != current_user_id:
        raise BusinessException(RESOURCE_NOT_FOUND, "素材不存在")

    binding = ProjectAsset(project_id=project_id, asset_id=asset_id, role=req.get("role", "reference"))
    asset.scope = "project"
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return Response.success(data={
        "id": binding.id,
        "project_id": project_id,
        "asset_id": asset_id,
        "role": binding.role,
    })


@router.get("/tasks/{task_id}", response_model=Response)
async def get_generation_task(
    task_id: str = Path(..., min_length=1),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询生成任务状态。"""
    try:
        result = await task_event_service.get_task_snapshot(db, task_id)
        return Response.success(data=result)
    except PermissionError:
        raise BusinessException(UNAUTHORIZED, "无权访问该任务")
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"任务不存在: {task_id}")


@router.get("/tasks/{task_id}/steps", response_model=Response)
async def get_generation_task_steps(
    task_id: str = Path(..., min_length=1),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询生成任务步骤。"""
    try:
        result = await task_event_service.get_task_steps(db, task_id)
        return Response.success(data=result)
    except PermissionError:
        raise BusinessException(UNAUTHORIZED, "无权访问该任务")
    except ValueError:
        raise BusinessException(RESOURCE_NOT_FOUND, f"任务不存在: {task_id}")


@router.post("/projects/{project_id}/workflow/confirm", response_model=Response)
async def confirm_workflow_stage(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """确认当前工作流阶段（不触发下一阶段任务）。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    from backend.v1.app.models.project import Project

    stage = req.get("stage")
    if not stage:
        raise BusinessException(VIDEO_ERROR, "stage 不能为空")

    project_model = await _load_project_for_workflow_update(db, project_id)
    if not project_model:
        raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
    try:
        generation_workflow_service.confirm_stage(project_model, stage)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
    await db.commit()
    await db.refresh(project_model)
    return Response.success(data={
        "project_id": project_id,
        "workflow_stage": project_model.workflow_stage,
        "stage_status": project_model.stage_status,
        "dirty_stage": project_model.dirty_stage,
        "script_confirmed_at": project_model.script_confirmed_at.isoformat() if project_model.script_confirmed_at else None,
        "images_confirmed_at": project_model.images_confirmed_at.isoformat() if project_model.images_confirmed_at else None,
        "video_confirmed_at": project_model.video_confirmed_at.isoformat() if project_model.video_confirmed_at else None,
    })


@router.post("/projects/{project_id}/workflow/advance", response_model=Response)
async def advance_workflow_stage(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """确认当前阶段并推进到下一工作流阶段，自动触发对应的任务生成。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    from backend.v1.app.models.project import Project

    confirmed_stage = req.get("confirmed_stage")
    if not confirmed_stage:
        raise BusinessException(VIDEO_ERROR, "confirmed_stage 不能为空")

    project_model = await _load_project_for_workflow_update(db, project_id)
    if not project_model:
        raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
    if project_model.stage_status == "running":
        return Response.success(data={
            "project_id": project_id,
            "workflow_stage": project_model.workflow_stage,
            "stage_status": project_model.stage_status,
            "dirty_stage": project_model.dirty_stage,
            "task_id": project_model.last_task_id,
            "next_stage": project_model.workflow_stage,
            "message": "任务已在运行中",
        })
    try:
        generation_workflow_service.advance_stage(project_model, confirmed_stage)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))

    task_result = None
    if project_model.workflow_stage == "video":
        task_result = await video_generation_service.submit_generation_task(db, project_id)
    elif project_model.workflow_stage == "image":
        task_result = await image_workflow_service.submit_image_task(db, project_id)
    await db.commit()
    await db.refresh(project_model)
    return Response.success(data={
        "project_id": project_id,
        "workflow_stage": project_model.workflow_stage,
        "stage_status": project_model.stage_status,
        "dirty_stage": project_model.dirty_stage,
        "task_id": task_result.get("task_id") if task_result else project_model.last_task_id,
        "next_stage": project_model.workflow_stage,
        "next_action": None,
    })


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
        metadata = {
            "display_content": req.get("display_content"),
            "selected_assets": req.get("selected_assets") or [],
            "local_references": req.get("local_references") or [],
            "client_id": req.get("client_id"),
            "assistant_client_id": req.get("assistant_client_id"),
        }
        if not content:
            raise BusinessException(VIDEO_ERROR, "content 不能为空")
        result = await chat_service.handle_message(db, project_id, content, frame_id, metadata=metadata)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/projects/{project_id}/chat/stream")
async def chat_stream(
    req: dict = Body(...),
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """流式对话端点：SSE 逐事件返回结果。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")
    content = req.get("content", "")
    frame_id = req.get("frame_id")
    metadata = {
        "display_content": req.get("display_content"),
        "selected_assets": req.get("selected_assets") or [],
        "local_references": req.get("local_references") or [],
        "client_id": req.get("client_id"),
        "assistant_client_id": req.get("assistant_client_id"),
    }
    if not content:
        raise BusinessException(VIDEO_ERROR, "content 不能为空")

    async def stream_events():
        try:
            async for event in chat_service.handle_message_stream(
                db,
                project_id,
                content,
                frame_id,
                metadata=metadata,
            ):
                yield event
        except Exception as exc:
            logger.exception("[chat_stream] stream failed project_id=%s", project_id)
            payload = json.dumps({"message": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/analyze-reference", response_model=Response)
async def analyze_chat_reference(
    file: UploadFile = File(..., description="参考图片"),
    current_user_id: int = Depends(get_current_user_id),
):
    """上传参考图片并解析特征，用于对话中作为参考素材。"""
    import uuid as _uuid
    from backend.v1.app.pipeline import ProductParsingPipeline
    from backend.store import get_storage_client
    from backend.store.obj.local_client import get_local_storage_client

    # 1. 上传图片到存储
    ext = (file.filename or "jpg").rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    object_name = f"chat-ref/{_uuid.uuid4().hex}.{ext}"
    stream = file.file
    if hasattr(stream, "seek"):
        stream.seek(0)
    try:
        url = get_storage_client().upload_fileobj(stream, object_name, file.content_type)
    except Exception:
        if hasattr(stream, "seek"):
            stream.seek(0)
        url = get_local_storage_client().upload_fileobj(stream, object_name, file.content_type)

    # 2. 走 product pipeline 解析图片特征
    features = {}
    try:
        pipeline = ProductParsingPipeline(enable_persistence=False, persist_to_asset=False)
        result = pipeline.run({"images": [url]})
        if result.get("success"):
            product_data = result.get("data", {}).get("product_data", {}) or {}
            basic_info = product_data.get("basic_info", {}) or {}
            raw_tags = product_data.get("tags", []) or []
            visual_features = raw_tags if isinstance(raw_tags, list) else [raw_tags]

            selling_points = product_data.get("selling_points", []) or []
            audience = basic_info.get("target_audience", "") or ""
            scenarios = basic_info.get("scenarios", []) or []
            keywords = product_data.get("keywords", []) or []

            # 构建 reference_text
            ref_lines = []
            if selling_points:
                ref_lines.append("Product selling point reference: " + "; ".join(str(s) for s in selling_points))
            if visual_features:
                ref_lines.append("Visual feature reference: " + "; ".join(str(v) for v in visual_features))
            if audience:
                ref_lines.append(f"Audience: {audience}")
            if scenarios:
                ref_lines.append("Scenarios: " + "; ".join(str(s) for s in scenarios))
            if keywords:
                ref_lines.append("Keywords: " + "; ".join(str(k) for k in keywords))

            features = {
                "selling_points": selling_points,
                "visual_features": visual_features,
                "audience": audience,
                "scenarios": scenarios,
                "keywords": keywords,
                "reference_text": "\n".join(ref_lines),
            }
    except Exception as exc:
        logger.warning("[analyze_chat_reference] image analysis failed: %s", exc)

    return Response.success(data={
        "id": uuid.uuid4().hex,
        "url": url,
        "features": features,
    })


@router.post("/chat/entry/stream")
async def chat_entry_stream(
    req: dict = Body(...),
    current_user_id: int = Depends(get_current_user_id),
):
    """Classify and answer messages before a project exists."""
    content = (req.get("content") or "").strip()
    if not content:
        raise BusinessException(VIDEO_ERROR, "content 不能为空")

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_events():
        try:
            # 先发 thinking 事件，让前端有反馈
            yield sse("thinking", {"message": "正在理解你的意图..."})

            # 使用LLM意图识别，失败时降级到硬编码规则
            try:
                intent = intent_service.classify_entry(content)
                action = "CREATE_PROJECT" if intent["should_create_project"] else "CONVERSE"
            except Exception as e:
                logger.warning(f"LLM intent failed, fallback to rule: {e}")
                fallback = classify_no_project_message(content)
                intent = {"should_create_project": fallback["should_create_project"]}
                action = fallback["action"]

            yield sse("start", {"action": action, "should_create_project": intent["should_create_project"]})
            if intent["should_create_project"]:
                yield sse("done", {
                    "action": "CREATE_PROJECT",
                    "should_create_project": True,
                    "user_prompt": content,
                })
                return

            try:
                for chunk in intent_service.stream_entry_converse(content):
                    yield sse("token", {"content": chunk})
            except Exception as exc:
                logger.warning("[chat_entry_stream] LLM converse fallback: %s", exc)
                reply = "我先按普通问题回答，不会创建项目。你可以继续提问；如果想开始做视频，请直接告诉我产品和目标。"
                for char in reply:
                    yield sse("token", {"content": char})
            yield sse("done", {
                "action": "CONVERSE",
                "should_create_project": False,
            })
        except Exception as exc:
            logger.exception("[chat_entry_stream] stream failed")
            yield sse("error", {"message": f"请求处理失败: {exc}"})

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/pending-actions/{pending_action_id}/confirm", response_model=Response)
async def confirm_pending_action(
    project_id: int = Path(..., gt=0),
    pending_action_id: str = Path(..., min_length=1),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Confirm and execute a previously persisted chat pending action."""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "No permission to operate this project")
    try:
        result = await chat_service.confirm_pending_action(db, project_id, pending_action_id)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/projects/{project_id}/pending-actions/{pending_action_id}/cancel", response_model=Response)
async def cancel_pending_action(
    project_id: int = Path(..., gt=0),
    pending_action_id: str = Path(..., min_length=1),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a previously persisted chat pending action."""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "No permission to operate this project")
    try:
        result = await chat_service.cancel_pending_action(db, project_id, pending_action_id)
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
            "message_type": c.message_type,
            "stage": c.stage,
            "blocks": c.blocks or [],
            "action_type": c.action_type,
            "task_id": c.task_id,
            "metadata": c.metadata_ or {},
            "frame_id": c.frame_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in conversations
    ])


@router.get("/projects/{project_id}/scripts", response_model=Response)
async def list_project_scripts(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询项目脚本版本列表。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")
    scripts = await storyboard_service.list_scripts(db, project_id)
    return Response.success(data=scripts)


@router.get("/projects/{project_id}/scripts/{script_id}", response_model=Response)
async def get_project_script(
    project_id: int = Path(..., gt=0),
    script_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询项目脚本版本详情。"""
    project = await ProjectService.get_project(db, project_id)
    if project.get("user_id") != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")
    try:
        script = await storyboard_service.get_script(db, project_id, script_id)
        return Response.success(data=script)
    except ValueError as e:
        raise BusinessException(RESOURCE_NOT_FOUND, str(e))


@router.patch("/projects/{project_id}/frames/{frame_id}", response_model=Response)
async def update_project_frame(
    patch: dict = Body(...),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """保存分镜编辑草稿，并标记为待合成。"""
    try:
        project = await ProjectService.get_project(db, project_id)
        if project.get("user_id") != current_user_id:
            raise BusinessException(UNAUTHORIZED, "无权操作该项目")
        frame = await storyboard_service.update_frame(db, project_id, frame_id, patch)
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="已保存分镜修改，可继续重新生成图片。",
            message_type="text",
            stage=project.get("workflow_stage") or "script",
            action_type="storyboard_edit_save",
            frame_id=frame_id,
            metadata_={
                "source": "project_detail",
                "action": "storyboard_edit_save",
            },
        ))
        await db.commit()
        return Response.success(data=frame)
    except BusinessException:
        raise
    except ValueError as e:
        raise BusinessException(RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        logger.exception(f"[update_project_frame] project_id={project_id}, frame_id={frame_id}")
        raise BusinessException(VIDEO_ERROR, f"保存分镜失败: {e}")


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate", response_model=Response)
async def regenerate_frame(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """重新生成指定帧的脚本+图片"""
    try:
        project = await ProjectService.get_project(db, project_id)
        if project.get("user_id") != current_user_id:
            raise BusinessException(UNAUTHORIZED, "无权操作该项目")
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame(db, project_id, frame_id, instruction)
        return Response.success(data=result)
    except BusinessException:
        raise
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
    except Exception as e:
        logger.exception(f"[regenerate_frame] project_id={project_id}, frame_id={frame_id}")
        raise BusinessException(VIDEO_ERROR, f"重新生成失败: {e}")


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate-image", response_model=Response)
async def regenerate_frame_image(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """只重新生成指定帧的图片（脚本不变）"""
    try:
        project = await ProjectService.get_project(db, project_id)
        if project.get("user_id") != current_user_id:
            raise BusinessException(UNAUTHORIZED, "无权操作该项目")
        instruction = (req or {}).get("instruction")
        result = await chat_service.regenerate_frame_image(db, project_id, frame_id, instruction)
        task = await generation_task_service.create_task(db, project_id, "frame_image", status="queued")
        project_model = await _load_project_for_workflow_update(db, project_id)
        if not project_model:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
        generation_workflow_service.invalidate_from(project_model, "image")
        generation_workflow_service.mark_stage_running(project_model, "image", task.id)
        from backend.v1.app.generate.tasks.celery_app import celery_app
        sent = celery_app.send_task("generate_frame_image_task", args=[project_id, frame_id, task.id])
        await generation_task_service.set_celery_task_id(db, task.id, sent.id)
        result.update({"task_id": task.id, "status": "queued"})
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="已提交图片重新生成任务，完成后会在对话中展示新图。",
            message_type="stage_card",
            stage="image",
            blocks=[build_progress_block("image", "running", task.id, "已提交图片重新生成，正在为你更新分镜图片。")],
            action_type="storyboard_edit_regenerate_image",
            task_id=task.id,
            frame_id=frame_id,
            metadata_={
                "source": "project_detail",
                "action": "storyboard_edit_regenerate_image",
                "task_id": task.id,
            },
        ))
        await db.commit()
        return Response.success(data=result)
    except BusinessException:
        raise
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
    except Exception as e:
        logger.exception(f"[regenerate_frame_image] project_id={project_id}, frame_id={frame_id}")
        raise BusinessException(VIDEO_ERROR, f"图片重新生成失败: {e}")


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate-video", response_model=Response)
async def regenerate_frame_video(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """提交单分镜视频重生成任务，成功后只更新该分镜视频产物，不自动整片合成。"""
    try:
        project = await ProjectService.get_project(db, project_id)
        if project.get("user_id") != current_user_id:
            raise BusinessException(UNAUTHORIZED, "无权操作该项目")
        from backend.v1.app.models.frame import Frame

        result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
        frame = result.scalar_one_or_none()
        if not frame:
            raise BusinessException(RESOURCE_NOT_FOUND, f"分镜不存在: {frame_id}")
        if not frame.image_url or frame.status != 2 or frame.dirty:
            raise BusinessException(VIDEO_ERROR, "请先重新生成图片，确认当前分镜有最新图片后再生成视频。")

        instruction = (req or {}).get("instruction")
        if instruction:
            ai_params = dict(frame.ai_params or {})
            ai_params["video_revision_instruction"] = instruction
            frame.ai_params = ai_params
        task = await generation_task_service.create_task(db, project_id, "frame_video", status="queued")
        project_model = await _load_project_for_workflow_update(db, project_id)
        if not project_model:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
        generation_workflow_service.invalidate_from(project_model, "video")
        generation_workflow_service.mark_stage_running(project_model, "video", task.id)
        frame.dirty = 1
        await db.commit()
        from backend.v1.app.generate.tasks.celery_app import celery_app
        sent = celery_app.send_task("generate_frame_video_task", args=[project_id, frame_id, task.id])
        await generation_task_service.set_celery_task_id(db, task.id, sent.id)
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="已提交分镜视频重新生成任务，完成后可在分镜编辑中预览。",
            message_type="stage_card",
            stage="video",
            blocks=[build_progress_block("video", "running", task.id, "已提交视频重新生成，正在为你更新分镜视频。")],
            action_type="storyboard_edit_regenerate_video",
            task_id=task.id,
            frame_id=frame_id,
            metadata_={
                "source": "project_detail",
                "action": "storyboard_edit_regenerate_video",
                "task_id": task.id,
            },
        ))
        await db.commit()
        return Response.success(data={
            "project_id": project_id,
            "frame_id": frame_id,
            "task_id": task.id,
            "status": "queued",
            "message": "单分镜视频重生成任务已提交",
        })
    except BusinessException:
        raise
    except Exception as e:
        logger.exception(f"[regenerate_frame_video] project_id={project_id}, frame_id={frame_id}")
        raise BusinessException(VIDEO_ERROR, f"视频重新生成失败: {e}")


@router.post("/projects/{project_id}/tts/regenerate", response_model=Response)
async def regenerate_project_tts(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """提交项目级 TTS 重生成任务，不直接覆盖成片视频。"""
    try:
        project = await ProjectService.get_project(db, project_id)
        if project.get("user_id") != current_user_id:
            raise BusinessException(UNAUTHORIZED, "无权操作该项目")
        result = await chat_service.submit_project_tts_regeneration_task(db, project_id)
        result.update({
            "project_id": project_id,
            "message": "项目配音重生成任务已提交",
        })
        return Response.success(data=result)
    except BusinessException:
        raise
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
    except Exception as e:
        logger.exception(f"[regenerate_project_tts] project_id={project_id}")
        raise BusinessException(VIDEO_ERROR, f"TTS 重生成失败: {e}")


@router.post("/projects/{project_id}/frames/{frame_id}/retry", response_model=Response)
async def retry_frame(
    req: dict | None = Body(None),
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """重试失败分镜并提交整片重新渲染。"""
    try:
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
        task_type = "frame_video" if frame.image_url and str(frame.image_url).startswith("http") else "frame_image"
        task = await generation_task_service.create_task(db, project_id, task_type, status="queued")
        project_model = await _load_project_for_workflow_update(db, project_id)
        if not project_model:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
        if task_type == "frame_video":
            generation_workflow_service.invalidate_from(project_model, "video")
            frame.dirty = 1
        else:
            generation_workflow_service.invalidate_from(project_model, "image")
            frame.image_url = None
            frame.dirty = 1
        await db.commit()

        from backend.v1.app.generate.tasks.celery_app import celery_app
        if task_type == "frame_video":
            sent = celery_app.send_task("generate_frame_video_task", args=[project_id, frame_id, task.id])
        else:
            sent = celery_app.send_task("generate_frame_image_task", args=[project_id, frame_id, task.id])
        await generation_task_service.set_celery_task_id(db, task.id, sent.id)
        return Response.success(data={
            "frame_id": frame_id,
            "project_id": project_id,
            "task_id": task.id,
            "status": "queued",
            "task_type": task_type,
        })
    except BusinessException:
        raise
    except Exception as e:
        logger.exception(f"[retry_frame] project_id={project_id}, frame_id={frame_id}")
        raise BusinessException(VIDEO_ERROR, f"重试失败: {e}")
