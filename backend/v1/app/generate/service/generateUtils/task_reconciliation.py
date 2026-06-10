"""Helpers for repairing orphaned generation tasks."""

from __future__ import annotations

from datetime import datetime

from backend.v1.app.generate.service.workflow import state as project_workflow_state


ACTIVE_CELERY_STATES = {"PENDING", "RECEIVED", "STARTED", "RETRY"}


def reconcile_orphaned_task(db, *, task, project, celery_state: str | None, error_message: str) -> bool:
    """Mark queued/running tasks as failed when their Celery worker is gone."""
    if task.status == "cancelled":
        return False
    if task.status not in {"queued", "running"}:
        return False
    if celery_state in ACTIVE_CELERY_STATES:
        return False

    task.status = "failed"
    task.current_step = "ORPHANED"
    task.error_code = "TASK_ORPHANED"
    task.error_message = error_message
    task.finished_at = datetime.utcnow()

    if project and getattr(project, "last_task_id", None) == getattr(task, "id", None):
        current_stage = getattr(project, "workflow_stage", None) or "video"
        if getattr(project, "stage_status", None) == "running":
            project_workflow_state.mark_project_stage_failed(project, current_stage, task.id)

    db.commit()
    return True
