from pathlib import Path


def test_script_generation_does_not_force_every_scene_to_minimum_four_seconds():
    source = Path("backend/v1/app/generate/service/stages/script.py").read_text(encoding="utf-8")

    assert "duration=max(4, scene.get(\"duration\", 5))" not in source


def test_video_generation_limits_tts_overrun_to_small_guard_window():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert "MAX_TTS_OVERRUN_SECONDS" in source
    assert "min(tts_duration, duration + MAX_TTS_OVERRUN_SECONDS)" in source


def test_tts_pipeline_adds_short_tail_padding_instead_of_unbounded_extension():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    ffmpeg_source = Path("backend/ffmpeg/pyutils.py").read_text(encoding="utf-8")

    assert "add_tail_padding_seconds" in source
    assert "append_tail_silence" in ffmpeg_source
    assert "TAIL_PADDING_SECONDS" in source
