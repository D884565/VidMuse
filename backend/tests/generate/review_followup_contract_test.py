from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")




def test_export_and_frame_tasks_have_real_celery_handlers():
    source = read("backend/v1/app/generate/tasks/video_tasks.py")

    assert 'name="generate_frame_video_task"' in source
    assert 'name="generate_frame_image_task"' in source
    assert "frame.dirty = 0" in source


def test_controller_dispatches_export_and_frame_tasks():
    source = read("backend/v1/app/generate/controller/generation.py")

    assert '"generate_frame_video_task"' in source
    assert '"generate_frame_image_task"' in source
    assert '"frame_image"' in source
    assert '"/projects/{project_id}/export/download"' in source


def test_core_paths_use_project_workflow_state_helper():
    for path in (
        "backend/v1/app/generate/service/video_generation.py",
        "backend/v1/app/generate/tasks/video_tasks.py",
        "backend/v1/app/generate/service/script_generation.py",
        "backend/v1/app/generate/service/chat/chat_service.py",
    ):
        source = read(path)
        assert "project_workflow_state" in source


def test_frontend_frame_grid_uses_export_and_timeline():
    source = read("frontend/src/components/Keyframes/FrameGrid.jsx")

    assert "downloadProjectVideo" in source
    assert "StoryboardTimeline" in source
    assert "导出" in source
