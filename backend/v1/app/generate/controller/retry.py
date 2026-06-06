"""重试 & 重新生成 API 路由"""
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import VIDEO_ERROR, RESOURCE_NOT_FOUND, UNAUTHORIZED
from backend.framework.web import Response
from backend.framework.web.auth import get_current_user_id
from backend.store.database.sync_database import get_db
from backend.v1.app.models.project import Project
from backend.v1.app.generate.service.generateUtils.retry_coordinator import retry_coordinator
from backend.v1.app.generate.service.generateUtils.task_tracker import generation_task_tracker
from backend.v1.app.generate.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["重试管理"])


def _get_project_owner(db: Session, project_id: int) -> Optional[int]:
    """获取项目所有者ID。"""
    project = db.execute(
        select(Project.user_id).where(Project.id == project_id)
    ).scalar_one_or_none()
    return project


class RetryRequest(BaseModel):
    """重试请求。"""
    stage: Optional[str] = None  # 指定阶段
    frames: Optional[list[int]] = None  # 指定帧
    force: bool = False  # 强制重试


class RegenerateFrameRequest(BaseModel):
    """单帧重新生成请求。"""
    type: str  # image 或 video
    reason: Optional[str] = None


@router.post("/projects/{project_id}/retry", response_model=Response)
def retry_generation(
    request: RetryRequest,
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """失败重试：从断点继续。"""
    owner_id = _get_project_owner(db, project_id)
    if owner_id != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")

    # 准备重试
    task_id, frames_to_retry = retry_coordinator.prepare_retry(
        db, project_id,
        stage=request.stage,
        frame_ids=request.frames,
    )

    # 确定阶段
    resume = retry_coordinator.determine_resume_point(db, project_id)
    stage = request.stage or resume.stage

    if stage == "start":
        raise BusinessException(VIDEO_ERROR, "没有失败的任务可以重试")

    # 派发 Celery 任务
    if stage == "image":
        celery_app.send_task("generate_image_task", args=[project_id, task_id])
    elif stage == "video":
        celery_app.send_task("generate_video_task", args=[project_id, task_id, "resume"])

    db.commit()

    return Response.success(data={
        "task_id": task_id,
        "resume_point": {
            "stage": stage,
            "frames_to_retry": frames_to_retry,
            "trigger_source": "resume",
        },
    })


@router.post("/projects/{project_id}/frames/{frame_id}/regenerate-frame", response_model=Response)
def regenerate_frame_retry(
    request: RegenerateFrameRequest,
    project_id: int = Path(..., gt=0),
    frame_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """用户修改：重新生成指定帧。"""
    owner_id = _get_project_owner(db, project_id)
    if owner_id != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权操作该项目")

    # 准备重试
    task_id, _ = retry_coordinator.prepare_retry(
        db, project_id,
        stage=request.type,
        frame_ids=[frame_id],
    )

    # 派发单帧任务
    if request.type == "image":
        celery_app.send_task("generate_frame_image_task", args=[project_id, frame_id, task_id])
    elif request.type == "video":
        celery_app.send_task("generate_frame_video_task", args=[project_id, frame_id, task_id])
    else:
        raise BusinessException(VIDEO_ERROR, f"无效的类型: {request.type}")

    db.commit()

    return Response.success(data={
        "task_id": task_id,
        "frame_id": frame_id,
        "type": request.type,
    })


@router.get("/projects/{project_id}/generation-status", response_model=Response)
def get_generation_status(
    project_id: int = Path(..., gt=0),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """查询任务状态。"""
    owner_id = _get_project_owner(db, project_id)
    if owner_id != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")

    status = retry_coordinator.get_generation_status(db, project_id)
    return Response.success(data=status)


@router.get("/projects/{project_id}/generation-frames", response_model=Response)
def get_generation_frames(
    project_id: int = Path(..., gt=0),
    stage: str = ...,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """查询帧级详情。"""
    owner_id = _get_project_owner(db, project_id)
    if owner_id != current_user_id:
        raise BusinessException(UNAUTHORIZED, "无权访问该项目")

    task = generation_task_tracker.get_latest_task(db, project_id)

    if not task:
        return Response.success(data={"stage": stage, "frames": []})

    frames = generation_task_tracker.get_frame_progress_list(db, task["task_id"], stage)
    return Response.success(data={"stage": stage, "frames": frames})
