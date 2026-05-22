"""剧本 Pydantic 模型"""
import datetime
from pydantic import BaseModel


class ScriptBase(BaseModel):
    title: str | None = None
    content: str
    target_duration: int | None = None
    ai_model: str | None = None
    ai_prompt: str | None = None


class ScriptResponse(ScriptBase):
    id: int
    project_id: int
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
