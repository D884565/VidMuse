from pathlib import Path


def test_render_task_only_generates_project_level_tts():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert source.count("tts_service.generate_audio(") == 1
    assert "FRAME_TTS_GENERATING" not in source
