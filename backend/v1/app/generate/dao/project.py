"""项目 Pydantic 模型"""
import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    title: str | None = None
    description: str | None = None
    product_url: str | None = None
    product_image: str | None = None
    product_info: str | None = None


class ProjectCreate(ProjectBase):
    title: str
    user_prompt: str | None = None
    reference_images: list[str] = Field(default_factory=list, max_length=5)
    style: str | None = None
    target_audience: str | None = None
    key_points: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    rag_weight: float = 0.3
    target_duration: int = 15
    voice_type: str = "zh_female_cancan_mars_bigtts"


class ProjectUpdate(ProjectBase):
    status: str | None = None
    video_output_url: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    status: str
    video_output_url: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    total: int
    items: list[ProjectResponse]
