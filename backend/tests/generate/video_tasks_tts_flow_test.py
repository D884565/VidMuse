from pathlib import Path


def test_tts_service_uses_retry_wrapper_for_http_post():
    source = Path("backend/providers/tts.py").read_text(encoding="utf-8")

    assert "def _request_with_retry" in source
    assert "self._request_with_retry(" in source
    assert "requests.post(" not in source


def test_render_task_builds_audio_from_frame_level_helpers():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert "_build_project_audio_track(" in source
    assert "_resolve_frame_narration_text(" in source
    assert "_resolve_frame_voice_type(" in source
    assert '(frames[0].ai_params or {}).get("voice_style", "")' not in source


def test_render_task_records_tts_observability_fields():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert '"trigger_source": trigger_source' in source
    assert '"fallback_used": tts_result.fallback_used' in source
    assert '"provider": tts_result.provider' in source


def test_celery_worker_registers_all_generation_tasks():
    from backend.v1.app.generate.tasks.celery_app import celery_app
    import backend.v1.app.generate.tasks.video_tasks  # noqa: F401

    expected = {
        "generate_image_task",
        "generate_video_task",
        "generate_project_tts_task",
        "generate_frame_image_task",
        "generate_frame_video_task",
    }

    assert expected.issubset(set(celery_app.tasks.keys()))


def test_celery_app_includes_real_generation_task_module():
    source = Path("backend/v1/app/generate/tasks/celery_app.py").read_text(encoding="utf-8")

    assert "backend.v1.app.generate.tasks.video_tasks" in source
    assert "backend.v1.app.generate.temp.video_tasks" not in source


def test_docker_celery_worker_uses_real_app_and_parallel_capacity_for_frame_tasks():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "celery -A backend.v1.app.generate.tasks.celery_app.celery_app worker" in source
    assert "--concurrency=${CELERY_WORKER_CONCURRENCY:-6}" in source
    assert "FRAME_VIDEO_WAIT_TIMEOUT_SECONDS" in source


def test_render_task_does_not_store_final_project_video_in_asset_library():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")

    assert 'title="成品视频"' not in source
    assert "source_type=1" not in source or "db.add(Asset(" not in source


def test_render_task_dispatches_frame_video_tasks_instead_of_serial_seedance_loop():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    render_body = source[
        source.index("def generate_video_task"):
        source.index("@celery_app.task", source.index("def generate_video_task") + 1)
    ]

    assert "def _generate_frame_videos_parallel(" in source
    assert '"generate_frame_video_task"' in source
    assert "_generate_frame_videos_parallel(" in render_body
    assert "video_composer.compose_frames(\n            frames," not in render_body


def test_tts_service_exposes_duration_and_concat_helpers():
    source = Path("backend/providers/tts.py").read_text(encoding="utf-8")

    assert "def create_silent_audio_for_duration" in source
    assert "def fit_audio_to_duration" in source
    assert "def concat_audio_clips" in source


def test_generation_controller_exposes_project_tts_regeneration_endpoint():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "/projects/{project_id}/tts/regenerate" in source
    assert "submit_project_tts_regeneration_task" in source


def test_render_task_finishes_as_reviewable_video_stage_not_completed():
    source = Path("backend/v1/app/generate/tasks/video_tasks.py").read_text(encoding="utf-8")
    completion_section = source[
        source.index("# ---- Step 6:"):
        source.index("db.add(Conversation(", source.index("# ---- Step 6:"))
    ]

    assert 'project_workflow_state.mark_project_stage_review(project, "video", task_id)' in completion_section
    assert "project_workflow_state.mark_project_completed(project, task_id)" not in completion_section
