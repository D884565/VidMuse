from pathlib import Path


def test_storyboard_service_supports_sequence_and_dirty_stage():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert '"sequence"' in source
    assert "invalidate_from" in source
    assert "validate_total_frame_duration" in source


def test_storyboard_service_uses_granular_invalidation_and_script_sync():
    source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert "_infer_dirty_stage" in source
    assert '"narration"' in source
    assert '"image_prompt"' in source
    assert '"video_prompt"' in source
    assert "_sync_project_script_snapshot" in source


def test_controller_exposes_frame_local_generation_routes():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/frames/{frame_id}/regenerate-image" in source
    assert "/frames/{frame_id}/regenerate-video" in source
    assert '"frame_video"' in source


def test_storyboard_detail_actions_write_conversation_audit_messages():
    generation_source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")
    storyboard_source = Path("backend/v1/app/generate/service/generateUtils/storyboard.py").read_text(encoding="utf-8")

    assert "Conversation(" in generation_source or "Conversation(" in storyboard_source
    assert "storyboard_edit" in generation_source or "storyboard_edit" in storyboard_source
    assert "frame_id" in generation_source


def test_retry_endpoint_does_not_submit_full_project_render_anymore():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    retry_start = source.index('async def retry_frame(')
    retry_end = source.find('@router', retry_start + 1)
    body = source[retry_start: retry_end if retry_end != -1 else len(source)]

    assert "submit_generation_task" not in body
    assert '"frame_video"' in body or '"frame_image"' in body
