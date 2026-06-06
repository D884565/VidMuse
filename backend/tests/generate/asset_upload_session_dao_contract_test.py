from pathlib import Path


def test_asset_upload_session_dao_exposes_crud_helpers():
    source = Path("backend/v1/app/assets/dao/asset_upload_session_dao.py").read_text(encoding="utf-8")

    assert "class AssetUploadSessionDAO" in source
    assert "create_session" in source
    assert "get_by_session_id" in source
    assert "update_session" in source
    assert "delete_session" in source

