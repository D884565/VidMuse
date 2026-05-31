from datetime import datetime

from backend.v1.app.generate.service.task_service import generation_task_service


class FakeSession:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.commits = 0
        self.refreshes = []

    def get(self, model, row_id):
        return self.rows.get((model, row_id))

    def add(self, row):
        self.added = row

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        self.refreshes.append(row)


class Task:
    id = 7
    status = "failed"
    started_at = None
    finished_at = datetime.utcnow()
    error_code = "OLD"
    error_message = "old error"
    current_step = "FAILED"
    current_frame_id = None
    progress = 100


def test_start_task_sync_raises_for_missing_task():
    db = FakeSession()

    try:
        generation_task_service.start_task_sync(db, 404, "IMAGE_GENERATING")
    except ValueError as exc:
        assert "generation task not found" in str(exc)
    else:
        raise AssertionError("expected missing task to raise")


def test_start_task_sync_rejects_terminal_task_without_restart_flag():
    from backend.v1.app.models.generation_task import GenerationTask

    task = Task()
    db = FakeSession({(GenerationTask, 7): task})

    try:
        generation_task_service.start_task_sync(db, 7, "IMAGE_GENERATING")
    except ValueError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("expected terminal task to be protected")


def test_start_task_sync_restart_clears_finished_and_error_fields():
    from backend.v1.app.models.generation_task import GenerationTask

    task = Task()
    db = FakeSession({(GenerationTask, 7): task})

    generation_task_service.start_task_sync(db, 7, "IMAGE_GENERATING", allow_restart=True)

    assert task.status == "running"
    assert task.current_step == "IMAGE_GENERATING"
    assert task.finished_at is None
    assert task.error_code is None
    assert task.error_message is None
    assert db.commits == 1


def test_start_step_sync_rejects_cancelled_task():
    from backend.v1.app.models.generation_task import GenerationTask

    task = Task()
    task.status = "cancelled"
    db = FakeSession({(GenerationTask, 7): task})

    try:
        generation_task_service.start_step_sync(db, 7, "VIDEO_GENERATING")
    except ValueError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("expected cancelled task to reject new step start")
