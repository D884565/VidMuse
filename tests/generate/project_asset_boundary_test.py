from pathlib import Path


def test_project_detail_does_not_return_all_user_assets():
    source = Path("backend/v1/app/generate/service/video_generation.py").read_text(encoding="utf-8")

    assert "Asset.user_id == project.user_id" not in source
    assert "ProjectAsset" in source
    assert "Asset.url.contains" not in source


def test_generation_controller_exposes_export_endpoint():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/projects/{project_id}/export" in source
    assert "/projects/{project_id}/export/download" in source


def test_project_detail_does_not_mix_final_video_into_assets():
    source = Path("backend/v1/app/generate/service/video_generation.py").read_text(encoding="utf-8")

    assert "video_asset_id" not in source
    assert "output_asset_result" not in source
    assert "Asset.url == project.video_output_url" not in source
