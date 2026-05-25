"""音视频合成 Pydantic 模型"""
from pydantic import BaseModel


class AudioReplaceRequest(BaseModel):
    """音频替换请求"""
    video_id: int
    audio_id: int


class BgmRequest(BaseModel):
    """添加BGM请求"""
    video_id: int
    bgm_id: int
    bgm_volume: float = 0.3
    original_volume: float = 1.0


class MixRequest(BaseModel):
    """多音轨混合请求"""
    video_id: int
    audio_ids: list[int]
    volumes: list[float] | None = None


class MergeTaskResponse(BaseModel):
    """合成任务响应"""
    task_id: str
    video_id: int
    status: str
    result: dict | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
