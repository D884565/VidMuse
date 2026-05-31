from pathlib import Path


def test_frame_model_has_separate_video_url_field():
    source = Path("backend/v1/app/models/frame.py").read_text(encoding="utf-8")

    assert "video_url" in source
    assert "帧视频片段URL" in source or "video segment" in source


def test_frame_video_task_writes_video_url_not_audio_url():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    start = source.index("def generate_frame_video_task")
    body = source[start:]

    assert "frame.video_url = video_url" in body
    assert "frame.audio_url = video_url" not in body


def test_project_detail_exposes_frame_video_url():
    source = Path("backend/v1/app/generate/service/video_generation.py").read_text(encoding="utf-8")

    assert '"video_url": f.video_url' in source
