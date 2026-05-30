from backend.v1.app.generate.service.project_workflow_state import (
    confirm_project_stage,
    invalidate_project_from,
    mark_project_completed,
    mark_project_stage_failed,
    mark_project_stage_review,
    mark_project_stage_running,
    set_project_workflow_state,
    sync_legacy_status,
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


def test_video_stage_review_requires_review_not_processing():
    project = Project()
    project.workflow_stage = "video"
    project.stage_status = "awaiting_review"

    sync_legacy_status(project)

    assert project.status == "review_required"


def test_invalidate_image_regresses_to_confirmed_script_with_dirty_marker():
    project = Project()
    project.workflow_stage = "image"
    project.stage_status = "awaiting_review"
    project.status = "review_required"
    project.script_confirmed_at = object()
    project.images_confirmed_at = object()
    project.video_confirmed_at = object()

    invalidate_project_from(project, "image")

    assert project.workflow_stage == "script"
    assert project.stage_status == "confirmed"
    assert project.status == "script_ready"
    assert project.dirty_stage == "image"
    assert project.script_confirmed_at is not None
    assert project.images_confirmed_at is None
    assert project.video_confirmed_at is None


def test_invalidate_video_regresses_to_confirmed_image_with_dirty_marker():
    project = Project()
    project.workflow_stage = "video"
    project.stage_status = "awaiting_review"
    project.status = "review_required"
    project.images_confirmed_at = object()
    project.video_confirmed_at = object()

    invalidate_project_from(project, "video")

    assert project.workflow_stage == "image"
    assert project.stage_status == "confirmed"
    assert project.status == "review_required"
    assert project.dirty_stage == "video"
    assert project.images_confirmed_at is not None
    assert project.video_confirmed_at is None


def test_mark_stage_review_clears_matching_dirty_stage():
    project = Project()
    project.workflow_stage = "script"
    project.stage_status = "confirmed"
    project.dirty_stage = "image"

    mark_project_stage_review(project, "image", task_id=8)

    assert project.dirty_stage is None
    assert project.workflow_stage == "image"
    assert project.stage_status == "awaiting_review"


def test_invalid_workflow_transition_is_rejected():
    project = Project()
    project.workflow_stage = "script"
    project.stage_status = "idle"

    try:
        set_project_workflow_state(project, "video", "running")
    except ValueError as exc:
        assert "invalid workflow transition" in str(exc)
    else:
        raise AssertionError("expected invalid transition to be rejected")


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


def test_confirm_stage_rejects_dirty_current_stage():
    project = Project()
    project.workflow_stage = "image"
    project.stage_status = "awaiting_review"
    project.status = "review_required"
    project.dirty_stage = "image"

    try:
        confirm_project_stage(project, "image")
    except ValueError as exc:
        assert "dirty" in str(exc)
    else:
        raise AssertionError("expected dirty current stage confirmation to be blocked")


def test_has_running_stage_task_detects_queued_or_running():
    tasks = [Task("image", "succeeded"), Task("image", "running")]

    assert has_running_stage_task(tasks, "image") is True
    assert has_running_stage_task(tasks, "render") is False
