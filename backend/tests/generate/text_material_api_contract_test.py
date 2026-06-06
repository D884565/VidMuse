from pathlib import Path


def test_asset_controller_has_text_material_routes():
    source = Path("backend/v1/app/assets/controller/asset_controller.py").read_text(encoding="utf-8")

    assert '/text' in source
    assert 'create_text_asset' in source
    assert 'update_text_asset' in source


def test_asset_service_has_text_material_methods():
    source = Path("backend/v1/app/assets/service/asset_service.py").read_text(encoding="utf-8")

    assert "create_text_asset" in source
    assert "update_text_asset" in source

