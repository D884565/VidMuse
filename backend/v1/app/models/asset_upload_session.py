"""Resumable upload session model."""

import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class AssetUploadSession(Base):
    __tablename__ = "asset_upload_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="Upload session ID")
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, comment="Related asset ID"
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, comment="Mode: create/replace")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="File name")
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="File hash")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="File size in bytes")
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="Chunk size")
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, comment="Total chunks")
    uploaded_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Uploaded chunk count")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="Session status")
    redis_bitmap_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="Redis bitmap key")
    temp_dir: Mapped[str] = mapped_column(String(500), nullable=False, comment="Temporary chunk directory")
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="Expiry time")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
