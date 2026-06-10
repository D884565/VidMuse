from types import SimpleNamespace


def test_update_task_failure_state_keeps_project_running_while_retrying(monkeypatch):
    from backend.v1.app.generate.tasks import video_tasks

    task_ref = SimpleNamespace(retry_count=1)
    project = SimpleNamespace(
        id=42,
        workflow_stage="video",
        stage_status="running",
        status="render_queued",
        last_task_id="gen_retry",
    )
    captured = {}

    class FakeSession:
        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(scalar_one_or_none=lambda: project)

        def commit(self):
            captured["committed"] = True

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(video_tasks, "_get_sync_db", lambda: FakeSession())
    monkeypatch.setattr(
        video_tasks.generation_task_service,
        "get_task_sync",
        lambda db, task_id: task_ref,
    )

    def fake_update_task_sync(db, task_id, **kwargs):
        captured["task_id"] = task_id
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        video_tasks.generation_task_service,
        "update_task_sync",
        fake_update_task_sync,
    )

    video_tasks._update_task_failure_state(
        task_id="gen_retry",
        project_id=42,
        stage="video",
        current_step="VIDEO_GENERATION_TIMEOUT",
        error_code="VIDEO_GENERATION_TIMEOUT",
        error_message="timeout",
        will_retry=True,
    )

    assert captured["task_id"] == "gen_retry"
    assert captured["kwargs"]["status"] == "queued"
    assert captured["kwargs"]["current_step"] == "RETRYING"
    assert captured["kwargs"]["retry_count"] == 2
    assert project.stage_status == "running"
    assert "committed" not in captured


def test_update_task_failure_state_marks_project_failed_after_final_video_failure(monkeypatch):
    from backend.v1.app.generate.tasks import video_tasks

    task_ref = SimpleNamespace(retry_count=2)
    project = SimpleNamespace(
        id=42,
        workflow_stage="video",
        stage_status="running",
        status="render_queued",
        dirty_stage=None,
        last_task_id="gen_final",
    )
    captured = {}

    class FakeSession:
        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(scalar_one_or_none=lambda: project)

        def commit(self):
            captured["committed"] = True

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(video_tasks, "_get_sync_db", lambda: FakeSession())
    monkeypatch.setattr(
        video_tasks.generation_task_service,
        "get_task_sync",
        lambda db, task_id: task_ref,
    )

    def fake_update_task_sync(db, task_id, **kwargs):
        captured["task_id"] = task_id
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        video_tasks.generation_task_service,
        "update_task_sync",
        fake_update_task_sync,
    )

    video_tasks._update_task_failure_state(
        task_id="gen_final",
        project_id=42,
        stage="video",
        current_step="VIDEO_SEGMENT_GENERATION_FAILED",
        error_code="VIDEO_SEGMENT_GENERATION_FAILED",
        error_message="failed frame ids: [3]",
        will_retry=False,
    )

    assert captured["task_id"] == "gen_final"
    assert captured["kwargs"]["status"] == "failed"
    assert captured["kwargs"]["current_step"] == "VIDEO_SEGMENT_GENERATION_FAILED"
    assert project.stage_status == "failed"
    assert project.status == "failed"
    assert project.last_task_id == "gen_final"
    assert captured["committed"] is True
