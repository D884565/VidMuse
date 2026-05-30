"""项目工作流状态同步工具。

这里是 workflow_stage、stage_status、dirty_stage 和 legacy status 的统一入口。
"""
from __future__ import annotations

from datetime import datetime


LEGACY_STATUS_BY_STAGE_STATUS = {
    ("created", "idle"): "draft",
    ("script", "idle"): "draft",
    ("script", "running"): "script_generating",
    ("script", "awaiting_review"): "script_ready",
    ("script", "confirmed"): "script_ready",
    ("script", "failed"): "failed",
    ("image", "idle"): "script_ready",
    ("image", "running"): "processing",
    ("image", "awaiting_review"): "review_required",
    ("image", "confirmed"): "review_required",
    ("image", "failed"): "failed",
    ("video", "idle"): "review_required",
    ("video", "running"): "render_queued",
    ("video", "awaiting_review"): "review_required",
    ("video", "confirmed"): "completed",
    ("video", "failed"): "failed",
    ("completed", "confirmed"): "completed",
}

NEXT_STAGE = {"script": "image", "image": "video", "video": "completed"}
REVIEWABLE_STATUSES = {"awaiting_review", "confirmed"}

VALID_TRANSITIONS = {
    ("created", "idle", "script", "running"),
    ("created", "idle", "script", "awaiting_review"),
    ("created", "idle", "image", "running"),
    ("created", "idle", "video", "running"),
    ("created", "idle", "video", "failed"),
    ("created", "idle", "completed", "confirmed"),
    ("script", "idle", "script", "running"),
    ("script", "failed", "script", "running"),
    ("script", "running", "script", "awaiting_review"),
    ("script", "awaiting_review", "script", "confirmed"),
    ("script", "awaiting_review", "video", "running"),
    ("script", "confirmed", "image", "idle"),
    ("script", "confirmed", "image", "running"),
    ("script", "confirmed", "image", "awaiting_review"),
    ("image", "idle", "image", "running"),
    ("image", "failed", "image", "running"),
    ("image", "running", "image", "awaiting_review"),
    ("image", "awaiting_review", "image", "confirmed"),
    ("image", "confirmed", "video", "idle"),
    ("image", "confirmed", "video", "running"),
    ("video", "idle", "video", "running"),
    ("video", "failed", "video", "running"),
    ("video", "running", "video", "awaiting_review"),
    ("video", "awaiting_review", "video", "confirmed"),
    ("video", "confirmed", "completed", "confirmed"),
    # 合法失效回退：保留上一个已确认阶段，用 dirty_stage 标记需要重做的阶段。
    ("image", "idle", "script", "confirmed"),
    ("image", "running", "script", "confirmed"),
    ("image", "awaiting_review", "script", "confirmed"),
    ("image", "confirmed", "script", "confirmed"),
    ("video", "idle", "image", "confirmed"),
    ("video", "running", "image", "confirmed"),
    ("video", "awaiting_review", "image", "confirmed"),
    ("video", "confirmed", "image", "confirmed"),
    ("completed", "confirmed", "video", "confirmed"),
}


def _set_task(project, task_id: int | None) -> None:
    if task_id is not None:
        project.last_task_id = task_id


def sync_legacy_status(project) -> None:
    """按新工作流字段同步旧 status 字段，旧接口只读这个缓存值。"""
    project.status = LEGACY_STATUS_BY_STAGE_STATUS.get(
        (project.workflow_stage, project.stage_status),
        "failed" if project.stage_status == "failed" else getattr(project, "status", "draft"),
    )


def set_project_workflow_state(
    project,
    stage: str,
    status: str,
    task_id: int | None = None,
    *,
    allow_regression: bool = False,
) -> None:
    """统一设置工作流状态，并校验阶段流转是否合法。"""
    old_stage = getattr(project, "workflow_stage", None) or "created"
    old_status = getattr(project, "stage_status", None) or "idle"
    transition = (old_stage, old_status, stage, status)
    same_state = old_stage == stage and old_status == status
    same_stage_operational = old_stage == stage and status in {"running", "awaiting_review", "failed"}
    if not allow_regression and not same_state and transition not in VALID_TRANSITIONS and not same_stage_operational:
        raise ValueError(f"invalid workflow transition: {old_stage}/{old_status} -> {stage}/{status}")

    project.workflow_stage = stage
    project.stage_status = status
    _set_task(project, task_id)
    sync_legacy_status(project)


def mark_project_stage_running(project, stage: str, task_id: int | None = None) -> None:
    """标记阶段运行中；dirty_stage 保留到成功产出后再清理。"""
    set_project_workflow_state(project, stage, "running", task_id)


def mark_project_stage_review(project, stage: str, task_id: int | None = None) -> None:
    """标记阶段已有新产物待审，若正好修复 dirty_stage 则清掉脏标记。"""
    set_project_workflow_state(project, stage, "awaiting_review", task_id)
    if getattr(project, "dirty_stage", None) == stage:
        project.dirty_stage = None


def mark_project_stage_failed(project, stage: str, task_id: int | None = None) -> None:
    """最终失败才调用；重试中不要把项目标成 failed。"""
    set_project_workflow_state(project, stage, "failed", task_id, allow_regression=True)


def mark_project_completed(project, task_id: int | None = None) -> None:
    """项目完成时清理所有脏标记。"""
    set_project_workflow_state(project, "completed", "confirmed", task_id)
    project.dirty_stage = None


def confirm_project_stage(project, stage: str) -> None:
    """确认当前阶段，但不自动推进到下一阶段。"""
    current_stage = getattr(project, "workflow_stage", None) or "script"
    if current_stage != stage:
        raise ValueError(f"cannot confirm {stage}: current stage is {current_stage}")
    if getattr(project, "dirty_stage", None) == stage:
        raise ValueError(f"cannot confirm dirty stage {stage}: regenerate this stage first")
    stage_status = getattr(project, "stage_status", None) or "idle"
    if stage_status not in REVIEWABLE_STATUSES:
        raise ValueError(f"stage {stage} is not reviewable (status={stage_status})")

    now = datetime.utcnow()
    if stage == "script":
        project.script_confirmed_at = now
    elif stage == "image":
        project.images_confirmed_at = now
    elif stage == "video":
        project.video_confirmed_at = now
    else:
        raise ValueError(f"unknown workflow stage: {stage}")
    set_project_workflow_state(project, stage, "confirmed")


def advance_project_stage(project, from_stage: str) -> None:
    """确认当前阶段并推进到下一阶段。"""
    confirm_project_stage(project, from_stage)
    target = NEXT_STAGE.get(from_stage)
    if not target:
        raise ValueError(f"unknown workflow stage: {from_stage}")
    target_status = "confirmed" if target == "completed" else "idle"
    set_project_workflow_state(project, target, target_status)


def invalidate_project_from(project, stage: str) -> None:
    """从指定阶段开始失效，并回退到上一个仍然有效的确认点。"""
    if stage == "script":
        target_stage, target_status = "script", "idle"
    elif stage == "image":
        target_stage, target_status = "script", "confirmed"
    elif stage == "video":
        target_stage, target_status = "image", "confirmed"
    else:
        raise ValueError(f"unknown workflow stage: {stage}")

    set_project_workflow_state(project, target_stage, target_status, allow_regression=True)
    project.dirty_stage = stage
    if stage == "script":
        project.script_confirmed_at = None
        project.images_confirmed_at = None
        project.video_confirmed_at = None
    elif stage == "image":
        project.images_confirmed_at = None
        project.video_confirmed_at = None
    elif stage == "video":
        project.video_confirmed_at = None
