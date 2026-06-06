from pathlib import Path


def test_asset_service_uses_library_scope_without_hardcoded_user_id():
    source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert '"user_id": 10001' not in source
    assert "scope='library'" in source or 'scope="library"' in source
    assert "scope=\"library\"" in source


def test_direct_image_reupload_endpoint_and_frontend_flow_exist():
    controller_source = Path("backend/v1/app/assets/controller/asset_controller.py").read_text(encoding="utf-8")
    service_source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")
    frontend_service_source = Path("frontend/src/services/asset.js").read_text(encoding="utf-8")
    media_grid_source = Path("frontend/src/components/Media/MediaGrid.jsx").read_text(encoding="utf-8")

    assert '@router.post("/{asset_id}/reupload"' in controller_source
    assert "reupload_image_asset" in service_source
    assert "reuploadImageAsset" in frontend_service_source
    assert "await reuploadImageAsset(" in media_grid_source


def test_frontend_material_library_is_scoped_to_text_and_image_only():
    source = Path("frontend/src/components/Media/MediaGrid.jsx").read_text(encoding="utf-8")

    assert "['all', 'image', 'text']" in source
    assert "accept=\"image/*\"" in source
    assert "video/*" not in source
    assert "audio/*" not in source
