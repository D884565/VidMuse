"""Small startup schema safeguards for tables required by current code."""

from backend.store.database.sync_database import engine
from backend.store.database.async_database import Base
from backend.v1.app.models.product_asset import ProductAsset


def ensure_product_assets_table() -> None:
    """Create product_assets when an existing local DB predates the table."""
    Base.metadata.create_all(bind=engine, tables=[ProductAsset.__table__], checkfirst=True)
