from types import SimpleNamespace

from backend.v1.app.generate.service.task_reconciliation import reconcile_orphaned_task


class FakeSession:
    def __init__(self, task, project):
        self.task = task
        self.project = project
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_reconcile_orphaned_running_task_marks_task_and_project_failed():
    task = SimpleNamespace(
        id=9,
        project_id=21,
        status="running",
        current_step="VIDEO_GENERATING",
        error_code=None,
        error_message=None,
        finished_at=None,
    )
    project = SimpleNamespace(
        id=21,
        workflow_stage="video",
        stage_status="running",
        status="render_queued",
        dirty_stage=None,
        last_task_id=9,
    )
    db = FakeSession(task, project)

    reconcile_orphaned_task(
        db,
        task=task,
        project=project,
        celery_state=None,
        error_message="worker heartbeat lost",
    )

    assert task.status == "failed"
    assert task.current_step == "ORPHANED"
    assert task.error_code == "TASK_ORPHANED"
    assert project.stage_status == "failed"
    assert project.status == "failed"
    assert db.commits == 1


def test_reconcile_cancelled_task_does_not_reopen_project_state():
    task = SimpleNamespace(
        id=10,
        project_id=22,
        status="cancelled",
        current_step="CANCELLED",
        error_code=None,
        error_message=None,
        finished_at=None,
    )
    project = SimpleNamespace(
        id=22,
        workflow_stage="video",
        stage_status="awaiting_review",
        status="review_required",
        dirty_stage=None,
        last_task_id=10,
    )
    db = FakeSession(task, project)

    reconcile_orphaned_task(
        db,
        task=task,
        project=project,
        celery_state=None,
        error_message="cancel already persisted",
    )

    assert task.status == "cancelled"
    assert project.stage_status == "awaiting_review"
    assert project.status == "review_required"
    assert db.commits == 0
