from backend.v1.app.generate.service.image_generation_service import ImageGenerationService
from backend.v1.app.generate.service.video_composer import VideoComposer


class Frame:
    def __init__(self, id=1, sequence=1, status=2, image_url="https://cdn.test/1.png"):
        self.id = id
        self.sequence = sequence
        self.status = status
        self.image_url = image_url
        self.description = "商品在桌面上"


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
