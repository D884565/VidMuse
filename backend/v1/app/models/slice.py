"""视频切片模型"""
import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Slice(Base):
    """视频切片表 ORM 模型"""
    __tablename__ = "slices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="切片ID")
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, comment="所属资产ID"
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False, comment="切片序号(从1开始)")
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="切片标题")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="切片视频存储URL")
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="切片封面图URL")
    start_time: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="切片在原视频中的开始时间(毫秒)")
    end_time: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="切片在原视频中的结束时间(毫秒)")
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="切片时长(毫秒)")
    ai_features: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI特征因子")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    # 关系：切片属于某个资产
    asset = relationship("Asset", back_populates="slices")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "index": self.index,
            "title": self.title,
            "url": self.url,
            "cover_url": self.cover_url,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "ai_features": self.ai_features,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
