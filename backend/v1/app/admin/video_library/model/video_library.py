"""内部视频素材库模型"""
import datetime
from sqlalchemy import String, BigInteger, Integer, DateTime, Text, JSON, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class VideoLibrary(Base):
    __tablename__ = "video_library"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="视频标题")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="视频描述")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="视频存储URL")
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="封面图URL")
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="文件大小(字节)")
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="视频时长(秒)")
    format: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="文件格式")
    source_type: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="来源：0-内部上传, 1-爆款抓取, 2-人工录入, 3-其他"
    )
    hot_score: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="爆款分数(0-100)")
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="视频分类/商品品类（冗余存储三级分类名称）")
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True, comment="关联分类ID，对应product_categories.id")
    category_path: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="分类路径，冗余存储方便检索，如\"/1/2/3/\"")
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="视频标签数组")
    parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="结构化解析数据")
    parsing_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="pending",
        comment="解析状态：pending/running/completed/failed"
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="流水线执行ID，用于断点续跑"
    )
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解析错误信息")
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, comment="关联的内部资产ID"
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="创建人ID(管理员ID)")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关系：关联到内部资产
    asset = relationship("Asset")

    # 关系：关联到商品分类
    category_obj = relationship("ProductCategory")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "cover_url": self.cover_url,
            "file_size": self.file_size,
            "duration": self.duration,
            "format": self.format,
            "source_type": self.source_type,
            "hot_score": self.hot_score,
            "category": self.category,
            "category_id": self.category_id,
            "category_path": self.category_path,
            "tags": self.tags,
            "parsed_data": self.parsed_data,
            "parsing_status": self.parsing_status,
            "execution_id": self.execution_id,
            "parsing_error": self.parsing_error,
            "asset_id": self.asset_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
