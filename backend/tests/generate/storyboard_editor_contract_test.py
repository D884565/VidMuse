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


def test_retry_endpoint_does_not_submit_full_project_render_anymore():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    retry_start = source.index('async def retry_frame(')
    retry_end = source.find('@router', retry_start + 1)
    body = source[retry_start: retry_end if retry_end != -1 else len(source)]

    assert "submit_generation_task" not in body
    assert '"frame_video"' in body or '"frame_image"' in body
