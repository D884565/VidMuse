"""项目工作流状态同步工具。

所有新入口都应通过这里更新 Project.status 与 workflow 字段，避免双轨状态漂移。
"""

LEGACY_STATUS_BY_STAGE_STATUS = {
    ("created", "idle"): "draft",
    ("script", "running"): "script_generating",
    ("script", "awaiting_review"): "script_ready",
    ("script", "confirmed"): "script_ready",
    ("image", "running"): "processing",
    ("image", "awaiting_review"): "script_ready",
    ("image", "confirmed"): "script_ready",
    ("video", "running"): "render_queued",
    ("video", "awaiting_review"): "processing",
    ("video", "confirmed"): "processing",
    ("completed", "confirmed"): "completed",
}


def _set_task(project, task_id: int | None) -> None:
    if task_id is not None:
        project.last_task_id = task_id


def sync_legacy_status(project) -> None:
    project.status = LEGACY_STATUS_BY_STAGE_STATUS.get(
        (project.workflow_stage, project.stage_status),
        "failed" if project.stage_status == "failed" else getattr(project, "status", "draft"),
    )


def mark_project_stage_running(project, stage: str, task_id: int | None = None) -> None:
    project.workflow_stage = stage
    project.stage_status = "running"
    _set_task(project, task_id)
    sync_legacy_status(project)


def mark_project_stage_review(project, stage: str, task_id: int | None = None) -> None:
    project.workflow_stage = stage
    project.stage_status = "awaiting_review"
    _set_task(project, task_id)
    sync_legacy_status(project)


def mark_project_stage_failed(project, stage: str, task_id: int | None = None) -> None:
    project.workflow_stage = stage
    project.stage_status = "failed"
    _set_task(project, task_id)
    sync_legacy_status(project)


def mark_project_completed(project, task_id: int | None = None) -> None:
    project.workflow_stage = "completed"
    project.stage_status = "confirmed"
    project.dirty_stage = None
    _set_task(project, task_id)
    sync_legacy_status(project)
