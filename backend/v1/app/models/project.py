"""视频项目模型。"""
import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    product_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="商品抓取结果 JSON")
    video_output_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="最终视频 URL")
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="项目 TTS 音频 URL")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="用户 ID")
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="商品 ID")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="项目状态: draft/script_ready/processing/completed/failed"
    )

    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户创作意图")
    reference_images: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="参考图片 URL 列表")
    style: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="视频风格")
    target_audience: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标受众")
    key_points: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="卖点列表")
    avoid: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="避免内容列表")
    rag_weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.3, comment="RAG 权重")
    target_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=15, comment="目标时长（秒）")
    voice_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="zh_female_cancan_mars_bigtts", comment="音色类型"
    )
    summary: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="对话摘要，用于侧边栏展示")

    # 工作流状态字段
    workflow_stage: Mapped[str] = mapped_column(String(30), nullable=False, default="created", server_default="created", comment="当前工作流阶段: created/script/image/video/completed")
    stage_status: Mapped[str] = mapped_column(String(30), nullable=False, default="idle", server_default="idle", comment="阶段状态: idle/running/awaiting_review/confirmed/failed")
    last_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="最近一次任务 ID")
    dirty_stage: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="脏标记：从此阶段开始需要重新确认")
    script_confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="剧本确认时间")
    images_confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="图片确认时间")
    video_confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="视频确认时间")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    frames = relationship("Frame", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
