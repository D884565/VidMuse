"""视频项目模型"""
import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, Numeric, func, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    product_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="商品信息JSON（抓取结果）")
    video_output_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="最终成片URL")
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="TTS配音音频URL")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="用户id")
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="商品id")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft/script_ready/processing/completed/failed"
    )

    # 用户输入字段
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户创作意图")
    reference_images: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="参考图片URL列表")
    style: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="视频风格")
    target_audience: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标受众")
    key_points: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="强调卖点列表")
    avoid: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="避免内容列表")
    rag_weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.3, comment="RAG权重0.00~1.00")
    target_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=15, comment="目标视频时长(秒)")
    voice_type: Mapped[str] = mapped_column(String(50), nullable=False, default="zh_female_cancan_mars_bigtts", comment="语音类型")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关联
    frames = relationship("Frame", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
