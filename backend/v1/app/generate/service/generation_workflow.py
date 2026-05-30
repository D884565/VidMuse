"""项目生成工作流状态机：管理 script -> image -> video 的阶段流转。"""
from __future__ import annotations

from datetime import datetime


# 阶段流转映射：当前阶段 -> 下一阶段
NEXT_STAGE = {
    "script": "image",
    "image": "video",
    "video": "completed",
}

# 可被用户确认的状态集合
REVIEWABLE_STATUSES = {"awaiting_review", "confirmed"}


class GenerationWorkflowService:
    """三阶段工作流状态机：剧本 -> 图片 -> 视频，每阶段支持确认/推进/失败/失效。"""

    def confirm_stage(self, project, stage: str) -> None:
        """确认当前阶段完成，不推进到下一阶段。"""
        current_stage = getattr(project, "workflow_stage", None) or "script"
        if current_stage != stage:
            raise ValueError(f"cannot confirm {stage}: 项目当前处于 {current_stage} 阶段")
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
            raise ValueError(f"未知的工作流阶段: {stage}")

        project.stage_status = "confirmed"
        project.dirty_stage = None

    def advance_stage(self, project, from_stage: str) -> None:
        """确认当前阶段并推进到下一阶段。"""
        self.confirm_stage(project, from_stage)
        project.workflow_stage = self.advance_target_for(from_stage)
        project.stage_status = "confirmed" if project.workflow_stage == "completed" else "idle"

    def mark_stage_running(self, project, stage: str, task_id: int | None = None) -> None:
        """标记指定阶段为运行中。"""
        project.workflow_stage = stage
        project.stage_status = "running"
        if task_id is not None:
            project.last_task_id = task_id

    def advance_target_for(self, confirmed_stage: str) -> str:
        """获取确认阶段后的下一个目标阶段。"""
        if confirmed_stage not in NEXT_STAGE:
            raise ValueError(f"未知的工作流阶段: {confirmed_stage}")
        return NEXT_STAGE[confirmed_stage]

    def mark_stage_review(self, project, stage: str, task_id: int | None = None) -> None:
        """标记阶段为待审核（生成完成后等待用户确认）。"""
        project.workflow_stage = stage
        project.stage_status = "awaiting_review"
        if task_id is not None:
            project.last_task_id = task_id

    def fail_stage(self, project, stage: str, task_id: int | None = None) -> None:
        """标记阶段为失败。"""
        project.workflow_stage = stage
        project.stage_status = "failed"
        if task_id is not None:
            project.last_task_id = task_id

    def invalidate_from(self, project, stage: str) -> None:
        """级联失效：从指定阶段开始，清除该阶段及后续阶段的确认时间，标记为脏。

        例如修改剧本时调用 invalidate_from(project, "script")，
        会清除 script/image/video 三个阶段的确认时间。
        """
        if stage not in NEXT_STAGE:
            raise ValueError(f"未知的工作流阶段: {stage}")

        project.workflow_stage = stage
        project.stage_status = "awaiting_review"
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


generation_workflow_service = GenerationWorkflowService()
