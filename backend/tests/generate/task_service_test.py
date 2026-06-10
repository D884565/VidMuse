from types import SimpleNamespace

import pytest

from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service


def test_start_task_sync_raises_for_missing_task(monkeypatch):
    def fake_snapshot(_db, _task_id):
        raise ValueError("task events not found")

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.get_task_snapshot_sync",
        fake_snapshot,
    )

    try:
        generation_task_service.start_task_sync(SimpleNamespace(), "gen_missing", "IMAGE_GENERATING")
    except ValueError as exc:
        assert "task events not found" in str(exc)
    else:
        raise AssertionError("expected missing task to raise")


def test_start_task_sync_rejects_terminal_task_without_restart_flag(monkeypatch):
    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.get_task_snapshot_sync",
        lambda _db, _task_id: {"status": "failed", "task_type": "render"},
    )

    try:
        generation_task_service.start_task_sync(SimpleNamespace(), "gen_failed", "IMAGE_GENERATING")
    except ValueError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("expected terminal task to be protected")


def test_start_task_sync_restart_emits_running_event(monkeypatch):
    emitted = {}
    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.get_task_snapshot_sync",
        lambda _db, _task_id: {
            "status": "failed",
            "task_type": "render",
            "project_id": 42,
            "trace_id": "trace_1",
            "progress": 100,
        },
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.emit_event_sync",
        lambda **kwargs: emitted.update(kwargs),
    )
    monkeypatch.setattr(generation_task_service, "_mirror_task_update_sync", lambda *args, **kwargs: None)

    generation_task_service.start_task_sync(
        SimpleNamespace(), "gen_failed", "IMAGE_GENERATING", allow_restart=True
    )

    assert emitted["task_id"] == "gen_failed"
    assert emitted["event_type"] == "task_started"
    assert emitted["status"] == "running"
    assert emitted["current_step"] == "IMAGE_GENERATING"


def test_start_step_sync_rejects_cancelled_task(monkeypatch):
    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.get_task_snapshot_sync",
        lambda _db, _task_id: {"status": "cancelled", "task_type": "render"},
    )

    try:
        generation_task_service.start_step_sync(SimpleNamespace(), "gen_cancelled", "VIDEO_GENERATING")
    except ValueError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("expected cancelled task to reject new step start")


def test_create_task_sync_returns_push_task_reference(monkeypatch):
    created = {}
    mirrored = {}

    def fake_create_task_sync(**kwargs):
        created.update(kwargs)
        return {
            "task_id": "gen_abc",
            "trace_id": "trace_1",
            "status": "queued",
            "progress": 0,
        }

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.create_task_sync",
        fake_create_task_sync,
    )
    monkeypatch.setattr(
        generation_task_service,
        "_mirror_task_created_sync",
        lambda _db, task_id, project_id, task_type, status: mirrored.update({
            "task_id": task_id,
            "project_id": project_id,
            "task_type": task_type,
            "status": status,
        }),
    )

    task = generation_task_service.create_task_sync(SimpleNamespace(), 42, "render", status="queued")

    assert task.id == "gen_abc"
    assert task.project_id == 42
    assert task.task_type == "render"
    assert task.status == "queued"
    assert task.trace_id == "trace_1"
    assert created["project_id"] == 42
    assert created["task_domain"] == "generation"
    assert created["task_type"] == "render"
    assert mirrored["task_id"] == "gen_abc"
    assert mirrored["project_id"] == 42
    assert mirrored["task_type"] == "render"
    assert mirrored["status"] == "queued"


@pytest.mark.asyncio
async def test_create_task_returns_push_task_reference(monkeypatch):
    created = {}
    allowed_sync_db = object()

    def fake_create_task_sync(**kwargs):
        created.update(kwargs)
        assert kwargs["db"] is allowed_sync_db
        return {
            "task_id": "gen_async",
            "trace_id": "trace_async",
            "status": "queued",
            "progress": 0,
        }

    class FakeAsyncSession:
        def __init__(self):
            self.sync_session = object()
            self.commits = 0
            self.run_sync_calls = 0

        async def commit(self):
            self.commits += 1

        async def flush(self):
            raise AssertionError("flush should not be called when commit=True")

        async def run_sync(self, fn, *args, **kwargs):
            self.run_sync_calls += 1
            return fn(allowed_sync_db, *args, **kwargs)

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.create_task_sync",
        fake_create_task_sync,
    )
    monkeypatch.setattr(generation_task_service, "_mirror_task_created_sync", lambda *args, **kwargs: None)

    db = FakeAsyncSession()
    task = await generation_task_service.create_task(db, 42, "render", status="queued")

    assert task.id == "gen_async"
    assert task.project_id == 42
    assert task.task_type == "render"
    assert task.status == "queued"
    assert task.trace_id == "trace_async"
    assert db.commits == 1
    assert db.run_sync_calls == 2


@pytest.mark.asyncio
async def test_set_celery_task_id_uses_run_sync(monkeypatch):
    emitted = {}
    mirrored = {}
    allowed_sync_db = object()

    def fake_emit_event_sync(**kwargs):
        emitted.update(kwargs)
        assert kwargs["db"] is allowed_sync_db

    class FakeAsyncSession:
        def __init__(self):
            self.sync_session = object()
            self.commits = 0
            self.run_sync_calls = 0

        async def commit(self):
            self.commits += 1

        async def run_sync(self, fn, *args, **kwargs):
            self.run_sync_calls += 1
            return fn(allowed_sync_db, *args, **kwargs)

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.emit_event_sync",
        fake_emit_event_sync,
    )
    monkeypatch.setattr(
        generation_task_service,
        "_mirror_celery_task_id_sync",
        lambda _db, task_id, celery_task_id: mirrored.update({
            "task_id": task_id,
            "celery_task_id": celery_task_id,
        }),
    )

    db = FakeAsyncSession()
    await generation_task_service.set_celery_task_id(db, "gen_async", "celery_123")

    assert db.run_sync_calls == 2
    assert db.commits == 1
    assert emitted["task_id"] == "gen_async"
    assert emitted["celery_task_id"] == "celery_123"
    assert mirrored["task_id"] == "gen_async"
    assert mirrored["celery_task_id"] == "celery_123"


def test_update_task_sync_mirrors_generation_task_snapshot(monkeypatch):
    emitted = {}
    mirrored = {}

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.get_task_snapshot_sync",
        lambda _db, _task_id: {
            "task_id": "gen_sync",
            "project_id": 51,
            "task_type": "render",
            "status": "running",
            "progress": 10,
            "trace_id": "trace_sync",
        },
    )
    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.emit_event_sync",
        lambda **kwargs: emitted.update(kwargs),
    )
    def fake_mirror_update(db, task_id, project_id, task_type, **kwargs):
        mirrored.update({
            "task_id": task_id,
            "project_id": project_id,
            "task_type": task_type,
            **kwargs,
        })

    monkeypatch.setattr(generation_task_service, "_mirror_task_update_sync", fake_mirror_update)

    generation_task_service.update_task_sync(
        SimpleNamespace(),
        "gen_sync",
        status="failed",
        progress=100,
        current_step="IMAGE_GENERATION_FAILED",
        error_code="IMAGE_GENERATION_FAILED",
        error_message="boom",
        retry_count=3,
    )

    assert emitted["task_id"] == "gen_sync"
    assert emitted["event_type"] == "task_failed"
    assert mirrored["task_id"] == "gen_sync"
    assert mirrored["project_id"] == 51
    assert mirrored["task_type"] == "render"
    assert mirrored["status"] == "failed"
    assert mirrored["progress"] == 100
    assert mirrored["current_stage"] == "IMAGE_GENERATION_FAILED"
    assert mirrored["error_code"] == "IMAGE_GENERATION_FAILED"
    assert mirrored["error_message"] == "boom"
    assert mirrored["retry_count"] == 3


def test_task_event_service_uses_non_committing_message_writes(monkeypatch):
    from backend.v1.app.push.service.task_event_service import task_event_service

    calls = []

    def fake_create_message(_db, _message_create, _message_id, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message_id=_message_id)

    monkeypatch.setattr(
        "backend.v1.app.push.dao.message_dao.message_dao.create_message",
        fake_create_message,
    )

    task_event_service.create_task_sync(
        db=SimpleNamespace(),
        task_domain="generation",
        task_type="script",
        project_id=25,
        user_id=1,
        commit=False,
    )
    task_event_service.emit_event_sync(
        db=SimpleNamespace(),
        task_id="gen_test",
        task_domain="generation",
        task_type="script",
        event_type="task_started",
        project_id=25,
        user_id=1,
        commit=False,
    )

    assert calls == [{"commit": False}, {"commit": False}]
