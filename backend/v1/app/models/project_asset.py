"""项目资产绑定模型。"""
import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class ProjectAsset(Base):
    __tablename__ = "project_assets"
    __table_args__ = (
        UniqueConstraint("project_id", "asset_id", "role", name="uq_project_assets_project_asset_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="reference")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
