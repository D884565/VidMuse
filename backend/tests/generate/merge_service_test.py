from types import SimpleNamespace

import pytest

from backend.v1.app.merge.service.merge_service import MergeService


@pytest.mark.asyncio
async def test_replace_audio_creates_push_task_event_and_dispatches_celery(monkeypatch):
    service = MergeService()
    db = SimpleNamespace(sync_session=SimpleNamespace())
    emitted = []
    dispatched = {}

    async def fake_get_asset(_db, asset_id):
        return SimpleNamespace(id=asset_id, url=f"https://cdn.test/{asset_id}.mp4", user_id=7)

    def fake_create_task_sync(**kwargs):
        emitted.append(kwargs)
        return {"task_id": "merge_abc", "status": "queued", "trace_id": "trace_1", "progress": 0}

    def fake_send_task(name, args=None, kwargs=None, task_id=None):
        dispatched.update({"name": name, "args": args, "kwargs": kwargs, "task_id": task_id})
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(service, "_get_asset", fake_get_asset)
    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.task_event_service.create_task_sync",
        fake_create_task_sync,
    )
    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.celery_app.send_task",
        fake_send_task,
    )

    result = await service.replace_audio(db, 11, 22)

    assert result["task_id"] == "merge_abc"
    assert result["status"] == "queued"
    assert emitted[0]["db"] is db.sync_session
    assert emitted[0]["task_domain"] == "merge"
    assert emitted[0]["task_type"] == "audio_replace"
    assert emitted[0]["asset_id"] == 11
    assert emitted[0]["extra"] == {"video_id": 11, "audio_id": 22}
    assert dispatched["name"] == "merge_replace_audio_task"
    assert dispatched["args"] == ["merge_abc"]
    assert dispatched["task_id"] == "merge_abc"


@pytest.mark.asyncio
async def test_cancel_merge_task_revokes_and_emits_cancel_event(monkeypatch):
    service = MergeService()
    class FakeDB:
        def __init__(self):
            self.sync_session = SimpleNamespace()
            self.commits = 0

        async def commit(self):
            self.commits += 1

    db = FakeDB()
    revoked = {}
    emitted = {}

    async def fake_status(_db, task_id):
        assert task_id == "merge_abc"
        return {"task_id": "merge_abc", "status": "queued", "task_type": "audio_replace"}

    def fake_emit(**kwargs):
        emitted.update(kwargs)

    def fake_revoke(task_id, terminate=False):
        revoked["task_id"] = task_id
        revoked["terminate"] = terminate

    monkeypatch.setattr(service, "get_task_status", fake_status)
    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.task_event_service.emit_event_sync",
        fake_emit,
    )
    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.celery_app.control.revoke",
        fake_revoke,
    )

    result = await service.cancel_task(db, "merge_abc")

    assert result["status"] == "cancelled"
    assert emitted["event_type"] == "task_cancelled"
    assert emitted["task_id"] == "merge_abc"
    assert emitted["task_domain"] == "merge"
    assert revoked == {"task_id": "merge_abc", "terminate": False}
    assert db.commits == 1
