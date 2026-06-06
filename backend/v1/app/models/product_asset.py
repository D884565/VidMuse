"""商品资产绑定模型。"""
import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class ProductAsset(Base):
    __tablename__ = "product_assets"
    __table_args__ = (
        UniqueConstraint("product_id", "asset_id", "role", name="uq_product_assets_product_asset_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="image", comment="资产角色：main-主素材, image-普通图片, video-视频, audio-音频")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
