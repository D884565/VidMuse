from pathlib import Path


def test_frontend_has_storyboard_timeline_component():
    source = Path("frontend/src/components/Workflow/StoryboardTimeline.jsx").read_text(encoding="utf-8")

    assert "dirty" in source
    assert "duration" in source
    assert "status" in source


def test_frontend_project_service_has_export_and_asset_methods():
    source = Path("frontend/src/services/project.js").read_text(encoding="utf-8")

    assert "exportProjectVideo" in source
    assert "bindProjectAsset" in source
