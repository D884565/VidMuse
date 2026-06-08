from backend.v1.app.generate.tasks import video_tasks


class _FakeDb:
    def __init__(self, label):
        self.label = label
        self.closed = False

    def close(self):
        self.closed = True


def test_wait_for_frame_video_tasks_reads_status_from_fresh_sessions(monkeypatch):
    stale_db = _FakeDb("stale")
    fresh_db = _FakeDb("fresh")

    def fake_get_sync_db():
        return fresh_db

    def fake_get_task_snapshot_sync(db, task_id):
        if db is stale_db:
            return {"task_id": task_id, "status": "running"}
        return {"task_id": task_id, "status": "succeeded"}

    monkeypatch.setattr(video_tasks, "_get_sync_db", fake_get_sync_db)
    monkeypatch.setattr(video_tasks.task_event_service, "get_task_snapshot_sync", fake_get_task_snapshot_sync)

    video_tasks._wait_for_frame_video_tasks(
        stale_db,
        ["gen_child_1"],
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )

    assert fresh_db.closed is True
