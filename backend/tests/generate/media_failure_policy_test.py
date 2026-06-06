from pathlib import Path

import pytest

from backend.v1.app.generate.service.stages.image_service import ImageGenerationService
from backend.v1.app.generate.service.stages.video_composer import VideoComposer


class Frame:
    def __init__(self, id=1, sequence=1, status=2, image_url="https://cdn.test/1.png"):
        self.id = id
        self.sequence = sequence
        self.status = status
        self.image_url = image_url
        self.video_url = None
        self.audio_url = None
        self.dirty = 0
        self.duration = 3
        self.description = "商品在桌面上"
        self.prompt = None
        self.ai_params = {}
        self.error_message = None


def test_video_composer_rejects_failed_frame_before_seedance_call():
    composer = VideoComposer()

    try:
        composer.validate_frames_for_video([Frame(status=3)])
    except ValueError as exc:
        assert "status == 3" in str(exc)
    else:
        raise AssertionError("expected failed frame to be rejected")


def test_video_composer_rejects_missing_image_url():
    composer = VideoComposer()

    try:
        composer.validate_frames_for_video([Frame(image_url=None)])
    except ValueError as exc:
        assert "missing image_url" in str(exc)
    else:
        raise AssertionError("expected missing image to be rejected")


def test_failed_image_does_not_write_placeholder_url_to_frame_image_url():
    service = ImageGenerationService()
    frame = Frame(status=0, image_url="https://cdn.test/old.png")

    def fail_generation(*args, **kwargs):
        raise RuntimeError("boom")

    service._call_text_to_image = fail_generation

    service.generate_frame_images([frame], project_id=1)

    assert frame.image_url is None
    assert frame.status == 3
    assert "boom" in frame.error_message


def test_completed_image_frame_is_skipped_without_api_call(monkeypatch):
    service = ImageGenerationService()
    frame = Frame(status=2, image_url="https://cdn.test/existing.png")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("completed frames should not call image generation APIs")

    monkeypatch.setattr(service, "_call_text_to_image", fail_if_called)
    monkeypatch.setattr(service, "_call_image_to_image", fail_if_called)

    result = service.generate_frame_images([frame], project_id=1)

    assert result == [frame]
    assert frame.image_url == "https://cdn.test/existing.png"
    assert frame.status == 2


def test_compose_frames_raises_when_segment_generation_fails_in_strict_mode(monkeypatch, tmp_path):
    composer = VideoComposer()
    frame = Frame(sequence=1)

    def fail_generate(*args, **kwargs):
        raise RuntimeError("seedance timeout")

    monkeypatch.setattr(composer.llm, "generate_video_sync", fail_generate)

    with pytest.raises(RuntimeError, match="seedance timeout"):
        composer.compose_frames([frame], str(tmp_path), allow_placeholder_segments=False)

    assert frame.status == 3
    assert "seedance timeout" in frame.error_message


def test_compose_frames_can_use_placeholder_when_explicitly_allowed(monkeypatch, tmp_path):
    composer = VideoComposer()
    frame = Frame(sequence=1)

    def fail_generate(*args, **kwargs):
        raise RuntimeError("seedance timeout")

    monkeypatch.setattr(composer.llm, "generate_video_sync", fail_generate)
    monkeypatch.setattr(
        composer,
        "_generate_placeholder_video",
        lambda output_dir, duration, index, message=None: str(tmp_path / "placeholder.mp4"),
    )

    result = composer.compose_frames([frame], str(tmp_path), allow_placeholder_segments=True)

    assert result.endswith("placeholder.mp4")
    assert frame.status == 3
    assert "seedance timeout" in frame.error_message


def test_compose_frames_reuses_clean_frame_video_without_seedance_call(monkeypatch, tmp_path):
    composer = VideoComposer()
    frame = Frame(sequence=1)
    frame.video_url = "https://cdn.test/frame.mp4"
    frame.dirty = 0

    def fail_if_called(*args, **kwargs):
        raise AssertionError("clean frame video should be reused")

    monkeypatch.setattr(composer.llm, "generate_video_sync", fail_if_called)

    def fake_download(_url, local_path):
        Path(local_path).write_bytes(b"video")

    monkeypatch.setattr(composer, "_download_video", fake_download)
    monkeypatch.setattr(composer, "_validate_local_video", lambda _path: None)

    result = composer.compose_frames([frame], str(tmp_path))

    assert result.endswith("_cached.mp4")
    assert frame.status == 2


def test_single_frame_video_regeneration_invalidates_video_stage():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert 'invalidate_from(project_model, "video")' in source


def test_full_render_path_persists_successful_frame_segments_for_retry_reuse():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert "_persist_frame_video_segment(" in source
    assert "frame.video_url = video_url" in source
    assert "frame.dirty = 0" in source


def test_full_render_persists_each_segment_immediately_via_callback():
    task_source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert 'celery_app.send_task("generate_frame_video_task"' in task_source
    assert "def generate_frame_video_task" in task_source
    assert "_persist_frame_video_segment(" in task_source
