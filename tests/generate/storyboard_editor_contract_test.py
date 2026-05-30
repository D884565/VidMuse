from pathlib import Path


def test_storyboard_service_supports_sequence_and_dirty_stage():
    source = Path("backend/v1/app/generate/service/storyboard_service.py").read_text(encoding="utf-8")

    assert '"sequence"' in source
    assert "invalidate_from" in source
    assert "validate_total_frame_duration" in source


def test_controller_exposes_frame_local_generation_routes():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/frames/{frame_id}/regenerate-image" in source
    assert "/frames/{frame_id}/regenerate-video" in source
    assert '"frame_video"' in source
