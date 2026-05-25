"""视频处理 Pydantic 模型"""
from pydantic import BaseModel


class VideoSplitRequest(BaseModel):
    """视频分段请求"""
    timestamps: list[float]


class VideoInfoResponse(BaseModel):
    """视频信息响应"""
    video_id: int
    duration: float
    width: int
    height: int
    format: str
    file_size: int
    fps: float


class VideoSplitResponse(BaseModel):
    """视频分段响应"""
    video_id: int
    duration: float
    segments: list[dict]
    total_segments: int
