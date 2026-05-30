from pathlib import Path


def test_render_task_only_generates_project_level_tts():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert source.count("tts_service.generate_audio(") == 1
    assert "FRAME_TTS_GENERATING" not in source


def test_celery_worker_registers_all_generation_tasks():
    from backend.v1.app.generate.temp.celery_app import celery_app
    import backend.v1.app.generate.temp.video_tasks  # noqa: F401

    expected = {
        "generate_image_task",
        "generate_video_task",
        "generate_frame_image_task",
        "generate_frame_video_task",
        "export_video_task",
    }

    assert expected.issubset(set(celery_app.tasks.keys()))
