from backend.v1.app.generate.service.project_workflow_state import (
    mark_project_completed,
    mark_project_stage_failed,
    mark_project_stage_review,
    mark_project_stage_running,
)
from backend.v1.app.generate.service.task_submission import has_running_stage_task


class Project:
    status = "draft"
    workflow_stage = "created"
    stage_status = "idle"
    dirty_stage = None
    last_task_id = None


class Task:
    def __init__(self, task_type, status):
        self.task_type = task_type
        self.status = status


def test_mark_project_stage_running_syncs_legacy_status():
    project = Project()

    mark_project_stage_running(project, "image", task_id=12)

    assert project.workflow_stage == "image"
    assert project.stage_status == "running"
    assert project.status == "processing"
    assert project.last_task_id == 12


def test_mark_project_stage_review_syncs_legacy_status():
    project = Project()

    mark_project_stage_review(project, "script", task_id=8)

    assert project.workflow_stage == "script"
    assert project.stage_status == "awaiting_review"
    assert project.status == "script_ready"
    assert project.last_task_id == 8


def test_mark_project_stage_failed_syncs_legacy_status():
    project = Project()

    mark_project_stage_failed(project, "video", task_id=21)

    assert project.workflow_stage == "video"
    assert project.stage_status == "failed"
    assert project.status == "failed"
    assert project.last_task_id == 21


def test_mark_project_completed_syncs_legacy_status():
    project = Project()
    project.dirty_stage = "video"

    mark_project_completed(project, task_id=99)

    assert project.workflow_stage == "completed"
    assert project.stage_status == "confirmed"
    assert project.status == "completed"
    assert project.dirty_stage is None
    assert project.last_task_id == 99


def test_has_running_stage_task_detects_queued_or_running():
    tasks = [Task("image", "succeeded"), Task("image", "running")]

    assert has_running_stage_task(tasks, "image") is True
    assert has_running_stage_task(tasks, "render") is False
