"""视频项目模型"""
import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    video_output_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="用户id")
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="商品id")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft/script_ready/processing/completed/failed"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关联
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
