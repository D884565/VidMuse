"""资产/素材模型"""
import datetime
import json
from sqlalchemy import String, BigInteger, Integer, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.store.database.async_database import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, comment="用户id"
    )
    type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="资产类型：1-图片, 2-视频, 3-音频"
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="资产标题")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="存储URL")
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="文件大小(字节)")
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="时长(视频/音频)")
    format: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="文件格式")
    ai_features: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI特征因子")
    source_type: Mapped[int] = mapped_column(
        Integer, default=0, comment="来源：0-上传, 1-AI生成, 2-爬取, 3-购买"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "url": self.url,
            "file_size": self.file_size,
            "duration": self.duration,
            "format": self.format,
            "ai_features": self.ai_features,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
