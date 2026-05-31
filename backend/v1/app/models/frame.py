"""分镜帧模型。"""
import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Frame(Base):
    __tablename__ = "frames"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_frames_project_sequence"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="frame id")
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="project id",
    )
    script_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("scripts.id", ondelete="SET NULL"),
        nullable=True,
        comment="script version id",
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, comment="frame sequence")
    scene_type: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="scene type")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="frame description")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="video prompt")
    narration: Mapped[str | None] = mapped_column(Text, nullable=True, comment="narration text")
    subtitle_text: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="subtitle text")
    subtitle_position: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="subtitle position")
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="image prompt")
    video_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="video prompt")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="frame image url")
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="frame audio url")
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="frame video segment url")
    text_overlay: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="text overlay")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="generation error")
    duration: Mapped[float] = mapped_column(
        Numeric(6, 3),
        nullable=False,
        server_default="3.000",
        comment="frame duration in seconds",
    )
    transition_type: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="transition")
    status: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="generation status")
    dirty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="dirty flag")
    last_edited_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    ai_params: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="ai params")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, comment="extra metadata")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project", back_populates="frames")
    script = relationship("Script", back_populates="frames")
