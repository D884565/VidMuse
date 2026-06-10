from pathlib import Path


def test_video_task_has_local_fallback_for_frame_video_generation():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert "def _run_frame_video_tasks_inline(" in source
    assert "worker_pool = getattr(celery_app.conf, \"worker_pool\", None)" in source
    assert "if worker_pool == \"solo\":" in source
    assert "_run_frame_video_tasks_inline(db, project_id, frames_to_generate)" in source
