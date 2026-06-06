from pathlib import Path


def test_asset_controller_has_resumable_upload_routes():
    source = Path("backend/v1/app/assets/controller/asset_controller.py").read_text(encoding="utf-8")

    assert "/upload/init" in source
    assert "/upload/chunk" in source
    assert "/upload/status" in source
    assert "/upload/complete" in source
    assert "/reupload/init" in source
    assert "/reupload/complete" in source


def test_asset_service_has_resumable_upload_methods():
    source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert "init_resumable_upload" in source
    assert "upload_image_chunk" in source
    assert "get_upload_status" in source
    assert "complete_resumable_upload" in source
    assert "init_image_reupload" in source
    assert "complete_image_reupload" in source

