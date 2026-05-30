"""兼容旧调用方的工作流服务门面。

实际状态流转统一委托给 project_workflow_state，避免 legacy status 漂移。
"""
from __future__ import annotations

from backend.v1.app.generate.service import project_workflow_state


class GenerationWorkflowService:
    """保留原类名，逐步把调用方迁移到 project_workflow_state。"""

    def confirm_stage(self, project, stage: str) -> None:
        project_workflow_state.confirm_project_stage(project, stage)

    def advance_stage(self, project, from_stage: str) -> None:
        project_workflow_state.advance_project_stage(project, from_stage)

    def mark_stage_running(self, project, stage: str, task_id: int | None = None) -> None:
        project_workflow_state.mark_project_stage_running(project, stage, task_id)

    def advance_target_for(self, confirmed_stage: str) -> str:
        try:
            return project_workflow_state.NEXT_STAGE[confirmed_stage]
        except KeyError as exc:
            raise ValueError(f"unknown workflow stage: {confirmed_stage}") from exc

    def mark_stage_review(self, project, stage: str, task_id: int | None = None) -> None:
        project_workflow_state.mark_project_stage_review(project, stage, task_id)

    def fail_stage(self, project, stage: str, task_id: int | None = None) -> None:
        project_workflow_state.mark_project_stage_failed(project, stage, task_id)

    def invalidate_from(self, project, stage: str) -> None:
        project_workflow_state.invalidate_project_from(project, stage)


generation_workflow_service = GenerationWorkflowService()
