"""Small startup schema safeguards for tables required by current code."""

from backend.store.database.sync_database import engine
from backend.store.database.async_database import Base

# Import all models so their tables are registered in Base.metadata
from backend.v1.app.models.product import Product
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.product_asset import ProductAsset


def ensure_product_assets_table() -> None:
    """Create product_assets and its dependent tables if they don't exist."""
    Base.metadata.create_all(bind=engine, checkfirst=True)
