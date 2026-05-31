from pathlib import Path


def test_tts_service_uses_retry_wrapper_for_http_post():
    source = Path("backend/v1/app/generate/service/tts_service.py").read_text(encoding="utf-8")

    assert "def _request_with_retry" in source
    assert "self._request_with_retry(" in source
    assert "requests.post(" not in source


def test_render_task_builds_audio_from_frame_level_helpers():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert "_build_project_audio_track(" in source
    assert "_resolve_frame_narration_text(" in source
    assert "_resolve_frame_voice_type(" in source
    assert '(frames[0].ai_params or {}).get("voice_style", "")' not in source


def test_render_task_records_tts_observability_fields():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert '"trigger_source": trigger_source' in source
    assert '"fallback_used": tts_result.fallback_used' in source
    assert '"provider": tts_result.provider' in source


def test_celery_worker_registers_all_generation_tasks():
    from backend.v1.app.generate.temp.celery_app import celery_app
    import backend.v1.app.generate.temp.video_tasks  # noqa: F401

    expected = {
        "generate_image_task",
        "generate_video_task",
        "generate_frame_image_task",
        "generate_frame_video_task",
    }

    assert expected.issubset(set(celery_app.tasks.keys()))


def test_render_task_does_not_store_final_project_video_in_asset_library():
    source = Path("backend/v1/app/generate/temp/video_tasks.py").read_text(encoding="utf-8")

    assert 'title="鎴愬搧瑙嗛"' not in source
    assert "source_type=1" not in source or "db.add(Asset(" not in source


def test_tts_service_exposes_duration_and_concat_helpers():
    source = Path("backend/v1/app/generate/service/tts_service.py").read_text(encoding="utf-8")

    assert "def create_silent_audio_for_duration" in source
    assert "def fit_audio_to_duration" in source
    assert "def concat_audio_clips" in source
