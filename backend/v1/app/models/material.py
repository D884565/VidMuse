"""素材模型"""
import datetime
from sqlalchemy import String, Text, BigInteger, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    script_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1=商品图 2=背景音乐 3=配音 4=字幕 5=成品视频"
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="MinIO路径")
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_features: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON")
    source_type: Mapped[int] = mapped_column(Integer, default=0, comment="0=上传 1=AI生成 2=模板")
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # 关联
    project = relationship("Project", back_populates="materials")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "script_id": self.script_id,
            "type": self.type,
            "title": self.title,
            "url": self.url,
            "file_size": self.file_size,
            "duration": self.duration,
            "format": self.format,
            "ai_features": self.ai_features,
            "source_type": self.source_type,
            "scene_index": self.scene_index,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
