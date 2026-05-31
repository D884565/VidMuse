from pathlib import Path


def test_project_asset_model_exists():
    source = Path("backend/v1/app/models/project_asset.py").read_text(encoding="utf-8")

    assert '__tablename__ = "project_assets"' in source
    assert "project_id" in source
    assert "asset_id" in source
    assert "uq_project_assets_project_asset_role" in source


def test_asset_model_has_structured_metadata_fields():
    source = Path("backend/v1/app/models/asset.py").read_text(encoding="utf-8")

    assert "tags" in source
    assert "scope" in source
    assert "metadata_" in source


def test_generation_controller_has_project_asset_binding_routes():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/projects/{project_id}/assets" in source
    assert "ProjectAsset" in source
