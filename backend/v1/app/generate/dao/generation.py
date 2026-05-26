"""生成任务 Pydantic 模型"""
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    """提交生成任务请求"""
    target_duration: int = 30
    voice_type: str = "zh-CN-XiaoxiaoNeural"


class GenerateResponse(BaseModel):
    """提交生成任务响应"""
    project_id: int
    frames_count: int | None = None
    status: str


class ProjectDetail(BaseModel):
    """项目详情（含帧和素材），供前端轮询用"""
    id: int
    title: str
    status: str
    video_url: str | None = None
    audio_url: str | None = None
    frames: list[dict] = []
    assets: list[dict] = []
    created_at: str
    updated_at: str
