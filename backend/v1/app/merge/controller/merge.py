"""音视频合成 API 路由"""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.merge.dao.merge import (
    AudioReplaceRequest,
    BgmRequest,
    MixRequest,
)
from backend.v1.app.merge.service.merge_service import merge_service
from backend.framework.web import Response
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR

router = APIRouter(prefix="/merge", tags=["音视频合成"])


@router.post("/audio-replace", response_model=Response)
async def replace_audio(
    req: AudioReplaceRequest,
    db: AsyncSession = Depends(get_db),
):
    """替换视频音频"""
    try:
        result = await merge_service.replace_audio(
            db, req.video_id, req.audio_id
        )
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/bgm", response_model=Response)
async def add_bgm(
    req: BgmRequest,
    db: AsyncSession = Depends(get_db),
):
    """添加背景音乐"""
    try:
        result = await merge_service.add_bgm(
            db, req.video_id, req.bgm_id,
            req.bgm_volume, req.original_volume
        )
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.post("/mix", response_model=Response)
async def mix_audio(
    req: MixRequest,
    db: AsyncSession = Depends(get_db),
):
    """混合多个音频轨道"""
    try:
        result = await merge_service.mix_audio_tracks(
            db, req.video_id, req.audio_ids, req.volumes
        )
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))


@router.get("/tasks/{task_id}", response_model=Response)
async def get_merge_task_status(
    task_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """查询合成任务状态"""
    try:
        status = await merge_service.get_task_status(db, task_id)
        return Response.success(data=status)
    except ValueError as e:
        raise BusinessException(RESOURCE_NOT_FOUND, str(e))


@router.post("/tasks/{task_id}/cancel", response_model=Response)
async def cancel_merge_task(
    task_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """取消合成任务"""
    try:
        result = await merge_service.cancel_task(db, task_id)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
