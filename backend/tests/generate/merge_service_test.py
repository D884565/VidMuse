from types import SimpleNamespace

import pytest

from backend.v1.app.merge.service.merge_service import MergeService


class FakeMergeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_replace_audio_dispatches_celery_task_using_persisted_merge_task_id(monkeypatch):
    service = MergeService()
    db = FakeMergeDB()
    dispatched = {}

    async def fake_get_asset(_db, asset_id):
        return SimpleNamespace(id=asset_id, url=f"https://cdn.test/{asset_id}.mp4")

    def fake_send_task(name, args=None, kwargs=None, task_id=None):
        dispatched["name"] = name
        dispatched["args"] = args
        dispatched["kwargs"] = kwargs
        dispatched["task_id"] = task_id
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(service, "_get_asset", fake_get_asset)
    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.celery_app.send_task",
        fake_send_task,
    )

    result = await service.replace_audio(db, 11, 22)

    assert result["task_id"].startswith("merge_")
    assert result["status"] == "queued"
    assert db.commits == 1
    assert dispatched["name"] == "merge_replace_audio_task"
    assert dispatched["args"] == [result["task_id"]]
    assert dispatched["task_id"] == result["task_id"]


@pytest.mark.asyncio
async def test_cancel_merge_task_revokes_same_task_id(monkeypatch):
    service = MergeService()
    revoked = {}
    task = SimpleNamespace(task_id="merge_abc", status="queued")

    class FakeScalarResult:
        def scalar_one_or_none(self):
            return task

    class FakeCancelDB:
        def __init__(self):
            self.commits = 0

        async def execute(self, _query):
            return FakeScalarResult()

        async def commit(self):
            self.commits += 1

    def fake_revoke(task_id, terminate=False):
        revoked["task_id"] = task_id
        revoked["terminate"] = terminate

    monkeypatch.setattr(
        "backend.v1.app.merge.service.merge_service.celery_app.control.revoke",
        fake_revoke,
    )

    result = await service.cancel_task(FakeCancelDB(), "merge_abc")

    assert result["status"] == "cancelled"
    assert task.status == "cancelled"
    assert revoked == {"task_id": "merge_abc", "terminate": False}
