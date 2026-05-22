"""项目 Pydantic 模型"""
import datetime
from pydantic import BaseModel


class ProjectBase(BaseModel):
    title: str | None = None
    description: str | None = None
    product_url: str | None = None
    product_image: str | None = None
    product_info: str | None = None


class ProjectCreate(ProjectBase):
    title: str


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
