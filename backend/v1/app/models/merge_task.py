"""音视频合成任务模型"""
import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.store.database.async_database import Base


class MergeTask(Base):
    """音视频合成任务"""
    __tablename__ = "merge_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="任务ID")
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="任务类型: audio_replace/bgm/mix"
    )
    video_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="视频资产ID")
    params: Mapped[str] = mapped_column(Text, nullable=False, comment="任务参数JSON")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued",
        comment="queued/processing/completed/failed/cancelled"
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务结果JSON")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
