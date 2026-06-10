"""Small startup schema safeguards for tables required by current code."""

import json
from pathlib import Path

from backend.store.database.sync_database import SessionLocal, engine
from backend.store.database.async_database import Base

# Import all models so their tables are registered in Base.metadata
from backend.v1.app.models.product import Product
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.product_asset import ProductAsset
from backend.v1.app.assets.dao.asset_dao import AssetDAO

ROOT = Path(__file__).resolve().parents[3]
SEED_BGM_ASSETS_PATH = ROOT / "resources" / "seed_bgm_assets.json"


def ensure_product_assets_table() -> None:
    """Create product_assets and its dependent tables if they don't exist."""
    Base.metadata.create_all(bind=engine, checkfirst=True)


def ensure_seed_bgm_assets() -> None:
    """Populate repo-managed BGM asset rows when they are missing."""
    if not SEED_BGM_ASSETS_PATH.exists():
        return

    seed_assets = json.loads(SEED_BGM_ASSETS_PATH.read_text(encoding="utf-8"))
    if not seed_assets:
        return

    db = SessionLocal()
    try:
        existing_urls = {
            url for (url,) in db.query(Asset.url).filter(Asset.type == 3).all() if url
        }
        missing_assets = []
        for item in seed_assets:
            asset_url = (item.get("url") or "").strip()
            if not asset_url or asset_url in existing_urls:
                continue
            missing_assets.append(
                {
                    "user_id": item.get("user_id"),
                    "type": 3,
                    "title": item.get("title"),
                    "url": asset_url,
                    "file_size": item.get("file_size"),
                    "duration": item.get("duration"),
                    "format": item.get("format") or "mp3",
                    "ai_features": item.get("ai_features"),
                    "tags": item.get("tags") or {},
                    "metadata_": item.get("metadata"),
                    "scope": item.get("scope") or {"type": "bgm_library"},
                    "content_text": item.get("content_text"),
                    "storage_key": item.get("storage_key"),
                    "file_hash": item.get("file_hash"),
                    "upload_status": item.get("upload_status"),
                    "upload_session_id": item.get("upload_session_id"),
                    "chunk_size": item.get("chunk_size"),
                    "total_chunks": item.get("total_chunks"),
                    "source_type": item.get("source_type", 2),
                    "parsing_status": item.get("parsing_status"),
                    "execution_id": item.get("execution_id"),
                    "parsing_error": item.get("parsing_error"),
                }
            )

        if missing_assets:
            AssetDAO.insert_batch_assets(db, missing_assets)
    finally:
        db.close()
