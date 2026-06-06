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

    task = generation_task_service.create_task_sync(SimpleNamespace(), 42, "render", status="queued")

    assert task.id == "gen_abc"
    assert task.project_id == 42
    assert task.task_type == "render"
    assert task.status == "queued"
    assert task.trace_id == "trace_1"
    assert created["project_id"] == 42
    assert created["task_domain"] == "generation"
    assert created["task_type"] == "render"


@pytest.mark.asyncio
async def test_create_task_returns_push_task_reference(monkeypatch):
    created = {}

    def fake_create_task_sync(**kwargs):
        created.update(kwargs)
        return {
            "task_id": "gen_async",
            "trace_id": "trace_async",
            "status": "queued",
            "progress": 0,
        }

    class FakeAsyncSession:
        def __init__(self):
            self.sync_session = SimpleNamespace()
            self.commits = 0

        async def commit(self):
            self.commits += 1

        async def flush(self):
            raise AssertionError("flush should not be called when commit=True")

    monkeypatch.setattr(
        "backend.v1.app.generate.service.generateUtils.task_service.task_event_service.create_task_sync",
        fake_create_task_sync,
    )

    db = FakeAsyncSession()
    task = await generation_task_service.create_task(db, 42, "render", status="queued")

    assert task.id == "gen_async"
    assert task.project_id == 42
    assert task.task_type == "render"
    assert task.status == "queued"
    assert task.trace_id == "trace_async"
    assert db.commits == 1
    assert created["db"] is db.sync_session
