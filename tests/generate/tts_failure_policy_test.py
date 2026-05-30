from pathlib import Path

from backend.v1.app.generate.service.tts_service import TtsResult


def test_tts_result_marks_fallback_explicitly():
    result = TtsResult(
        path="/tmp/test.mp3",
        fallback_used=True,
        provider="silent_fallback",
        warning="tts failed",
    )

    assert result.fallback_used is True
    assert result.provider == "silent_fallback"
    assert result.warning == "tts failed"


def test_render_task_treats_silent_fallback_as_failure_by_default():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert "if tts_result.fallback_used and not allow_degraded_audio:" in source
    assert "TTS_GENERATION_FAILED" in source
