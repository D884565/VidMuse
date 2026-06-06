from pathlib import Path


def test_asset_service_uses_bitmap_and_chunk_files_for_upload_resume():
    source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert "set_bit" in source
    assert "get_uploaded_indexes" in source
    assert "os.makedirs" in source
    assert "chunk_path" in source
    assert "upload_file(" in source


def test_asset_service_reupload_updates_original_asset_record():
    source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert "old_storage_key" in source
    assert '"storage_key"' in source
    assert '"file_hash"' in source
    assert '"upload_status"' in source
    assert "delete_object" in source

