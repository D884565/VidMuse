from pathlib import Path


def test_project_detail_does_not_return_all_user_assets():
    source = Path("backend/v1/app/generate/service/video_generation.py").read_text(encoding="utf-8")

    assert "Asset.user_id == project.user_id" not in source
    assert "ProjectAsset" in source
    assert "Asset.url.contains" not in source


def test_generation_controller_exposes_export_endpoint():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/projects/{project_id}/export" in source
    assert '"export"' in source
