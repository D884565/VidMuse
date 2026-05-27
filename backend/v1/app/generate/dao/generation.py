"""生成任务 Pydantic 模型"""
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """提交生成任务请求"""
    target_duration: int = 30
    voice_type: str = "zh-CN-XiaoxiaoNeural"
    user_prompt: str = Field(..., min_length=1, max_length=2000, description="用户创作意图描述")
    reference_images: list[str] = Field(default_factory=list, max_length=5, description="参考图片URL列表")
    style: str | None = Field(None, max_length=50, description="视频风格")
    target_audience: str | None = Field(None, max_length=100, description="目标受众")
    key_points: list[str] = Field(default_factory=list, description="需要强调的卖点")
    avoid: list[str] = Field(default_factory=list, description="需要避免的内容")
    rag_weight: float = Field(0.3, ge=0.0, le=1.0, description="RAG参考权重 0.0~1.0")


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
