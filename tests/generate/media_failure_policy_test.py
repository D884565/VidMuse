from pathlib import Path

from backend.v1.app.generate.service.video_composer import VideoComposer


class Frame:
    def __init__(self, id=1, sequence=1, status=2, image_url="https://cdn.test/1.png"):
        self.id = id
        self.sequence = sequence
        self.status = status
        self.image_url = image_url


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
    source = Path("backend/v1/app/generate/service/image_generation_service.py").read_text(encoding="utf-8")

    assert "frame.image_url = placeholder_url" not in source
    assert "frame.image_url = None" in source
    assert "frame.status == 2 and frame.image_url" in source
