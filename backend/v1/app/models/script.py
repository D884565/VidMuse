"""可编辑分镜工作流的脚本版本模型。"""
import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Script(Base):
    __tablename__ = "scripts"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_scripts_project_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    generation_mode: Mapped[str] = mapped_column(String(30), nullable=False, server_default="llm")
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rag_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("scripts.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="scripts")
    frames = relationship("Frame", back_populates="script")
