"""Asset/material model."""

import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, comment="User ID"
    )
    type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Asset type: 1-image, 2-video, 3-audio, 4-text"
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Asset title")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Storage URL")
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="File size in bytes")
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Duration for video/audio")
    format: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="File format")
    ai_features: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI feature payload")
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="Asset tags")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, comment="Extended metadata")
    scope: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="Asset scope")
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Text material content")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Object storage key")
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="File hash")
    upload_status: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="Upload status")
    upload_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Current upload session ID")
    chunk_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Chunk size")
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Total chunks")
    source_type: Mapped[int] = mapped_column(Integer, default=0, comment="Source type")
    parsing_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="Parsing status: pending/running/completed/failed"
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Pipeline execution ID for resume"
    )
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Parsing error")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    slices = relationship("Slice", back_populates="asset", cascade="all, delete-orphan")
    products = relationship("Product", secondary="product_assets", back_populates="assets")

    def to_dict(self) -> dict:
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
            "tags": self.tags,
            "scope": self.scope,
            "metadata": self.metadata_,
            "content_text": self.content_text,
            "storage_key": self.storage_key,
            "file_hash": self.file_hash,
            "upload_status": self.upload_status,
            "upload_session_id": self.upload_session_id,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "source_type": self.source_type,
            "parsing_status": self.parsing_status,
            "execution_id": self.execution_id,
            "parsing_error": self.parsing_error,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }

