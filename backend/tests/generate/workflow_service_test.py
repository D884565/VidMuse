from datetime import datetime

import pytest

from backend.v1.app.generate.service.generation_workflow import GenerationWorkflowService


class DummyProject:
    workflow_stage = "script"
    stage_status = "awaiting_review"
    dirty_stage = None
    script_confirmed_at = None
    images_confirmed_at = None
    video_confirmed_at = None
    last_task_id = None


def test_confirm_script_marks_stage_confirmed_without_advancing():
    project = DummyProject()

    GenerationWorkflowService().confirm_stage(project, "script")

    assert project.workflow_stage == "script"
    assert project.stage_status == "confirmed"
    assert isinstance(project.script_confirmed_at, datetime)


def test_advance_script_confirms_and_moves_project_to_image_stage():
    project = DummyProject()

    GenerationWorkflowService().advance_stage(project, "script")

    assert project.workflow_stage == "image"
    assert project.stage_status == "idle"
    assert isinstance(project.script_confirmed_at, datetime)


def test_confirm_image_marks_stage_confirmed_without_advancing():
    project = DummyProject()
    project.workflow_stage = "image"
    project.stage_status = "awaiting_review"

    GenerationWorkflowService().confirm_stage(project, "image")

    assert project.workflow_stage == "image"
    assert project.stage_status == "confirmed"
    assert isinstance(project.images_confirmed_at, datetime)


def test_confirm_stage_rejects_out_of_order_stage():
    project = DummyProject()

    with pytest.raises(ValueError, match="cannot confirm image"):
        GenerationWorkflowService().confirm_stage(project, "image")


def test_confirm_stage_rejects_non_reviewable_status():
    project = DummyProject()
    project.stage_status = "running"

    with pytest.raises(ValueError, match="not reviewable"):
        GenerationWorkflowService().confirm_stage(project, "script")


def test_mark_stage_running_sets_task_and_status():
    project = DummyProject()

    GenerationWorkflowService().mark_stage_running(project, "script", task_id=42)

    assert project.workflow_stage == "script"
    assert project.stage_status == "running"
    assert project.last_task_id == 42


def test_advance_target_for_returns_next_stage():
    service = GenerationWorkflowService()

    assert service.advance_target_for("script") == "image"
    assert service.advance_target_for("image") == "video"


def test_fail_stage_sets_failed_status_and_task():
    project = DummyProject()

    GenerationWorkflowService().fail_stage(project, "image", task_id=7)

    assert project.workflow_stage == "image"
    assert project.stage_status == "failed"
    assert project.last_task_id == 7


def test_invalidate_from_script_clears_later_confirmations():
    project = DummyProject()
    project.workflow_stage = "video"
    project.stage_status = "awaiting_review"
    project.script_confirmed_at = datetime.utcnow()
    project.images_confirmed_at = datetime.utcnow()
    project.video_confirmed_at = datetime.utcnow()

    GenerationWorkflowService().invalidate_from(project, "script")

    assert project.workflow_stage == "script"
    assert project.stage_status == "idle"
    assert project.dirty_stage == "script"
    assert project.script_confirmed_at is None
    assert project.images_confirmed_at is None
    assert project.video_confirmed_at is None


def test_invalidate_from_image_preserves_script_confirmation():
    project = DummyProject()
    script_confirmed_at = datetime.utcnow()
    project.workflow_stage = "video"
    project.script_confirmed_at = script_confirmed_at
    project.images_confirmed_at = datetime.utcnow()
    project.video_confirmed_at = datetime.utcnow()

    GenerationWorkflowService().invalidate_from(project, "image")

    assert project.workflow_stage == "script"
    assert project.stage_status == "confirmed"
    assert project.dirty_stage == "image"
    assert project.script_confirmed_at == script_confirmed_at
    assert project.images_confirmed_at is None
    assert project.video_confirmed_at is None
