from pathlib import Path


def test_asset_model_has_text_material_and_resumable_upload_fields():
    source = Path("backend/v1/app/models/asset.py").read_text(encoding="utf-8")

    assert "content_text" in source
    assert "storage_key" in source
    assert "file_hash" in source
    assert "upload_status" in source
    assert "upload_session_id" in source
    assert "chunk_size" in source
    assert "total_chunks" in source
    assert '4-text' in source or '4, "text"' or '4-text' in source


def test_asset_upload_session_model_exists_with_bitmap_fields():
    source = Path("backend/v1/app/models/asset_upload_session.py").read_text(encoding="utf-8")

    assert "class AssetUploadSession" in source
    assert "__tablename__ = \"asset_upload_sessions\"" in source
    assert "session_id" in source
    assert "asset_id" in source
    assert "mode" in source
    assert "file_hash" in source
    assert "chunk_size" in source
    assert "total_chunks" in source
    assert "uploaded_chunks" in source
    assert "redis_bitmap_key" in source
    assert "temp_dir" in source
    assert "status" in source


def test_schema_sql_documents_asset_material_and_upload_session_fields():
    init_sql_source = Path("resources/init.sql").read_text(encoding="utf-8")
    migration_source = Path(
        "docs/database/migrations/20260606_add_asset_material_resumable_upload.sql"
    ).read_text(encoding="utf-8")
    combined = init_sql_source + "\n" + migration_source

    assert "content_text" in combined
    assert "storage_key" in combined
    assert "file_hash" in combined
    assert "upload_status" in combined
    assert "upload_session_id" in combined
    assert "chunk_size" in combined
    assert "total_chunks" in combined
    assert "CREATE TABLE IF NOT EXISTS asset_upload_sessions" in combined
    assert "redis_bitmap_key" in combined

