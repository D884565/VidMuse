"""视频处理 API 路由"""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import get_db
from backend.v1.app.video.dao.video import VideoSplitRequest
from backend.v1.app.video.service.video_service import video_service
from backend.framework.web import Response
from backend.framework.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, VIDEO_ERROR

router = APIRouter(prefix="/video", tags=["视频处理"])


@router.get("/{video_id}/info", response_model=Response)
async def get_video_info(
    video_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """获取视频元数据信息（时长、分辨率、格式等）"""
    try:
        info = await video_service.get_video_info(db, video_id)
        return Response.success(data=info)
    except ValueError as e:
        raise BusinessException(RESOURCE_NOT_FOUND, str(e))


@router.post("/{video_id}/split", response_model=Response)
async def split_video(
    req: VideoSplitRequest,
    video_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    """按时间戳分段视频"""
    try:
        result = await video_service.split_video(db, video_id, req.timestamps)
        return Response.success(data=result)
    except ValueError as e:
        raise BusinessException(VIDEO_ERROR, str(e))
