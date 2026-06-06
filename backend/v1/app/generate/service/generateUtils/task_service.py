from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.v1.app.push.service.task_event_service import task_event_service


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@dataclass
class TaskReference:
    id: str
    project_id: int
    task_type: str
    status: str
    progress: int = 0
    trace_id: str | None = None
    celery_task_id: str | None = None
    current_step: str | None = None
    current_frame_id: int | None = None


@dataclass
class StepReference:
    task_id: str
    step_name: str
    frame_id: int | None = None
    progress: int = 0
    input_snapshot: dict[str, Any] | None = None


class GenerationTaskService:
    async def create_task(
        self,
        db: AsyncSession,
        project_id: int,
        task_type: str,
        *,
        status: str = "queued",
        trace_id: str | None = None,
        commit: bool = True,
    ) -> TaskReference:
        event = task_event_service.create_task_sync(
            db=db.sync_session,
            task_domain="generation",
            task_type=task_type,
            project_id=project_id,
            status=status,
            trace_id=trace_id,
        )
        if commit:
            await db.commit()
        else:
            await db.flush()
        return self._reference_from_event(event, project_id, task_type)

    async def set_celery_task_id(self, db: AsyncSession, task_id: str, celery_task_id: str) -> None:
        task_event_service.emit_event_sync(
            db=db.sync_session,
            task_id=task_id,
            task_domain="generation",
            task_type="unknown",
            event_type="celery_task_bound",
            status=None,
            progress=None,
            celery_task_id=celery_task_id,
        )
        await db.commit()

    async def get_task(self, db: AsyncSession, task_id: str, user_id: int | None = None) -> dict:
        return await task_event_service.get_task_snapshot(db, task_id)

    async def list_steps(self, db: AsyncSession, task_id: str, user_id: int | None = None) -> list[dict]:
        return await task_event_service.get_task_steps(db, task_id)

    def create_task_sync(
        self,
        db: Session,
        project_id: int,
        task_type: str,
        *,
        status: str = "queued",
        trace_id: str | None = None,
    ) -> TaskReference:
        event = task_event_service.create_task_sync(
            db=db,
            task_domain="generation",
            task_type=task_type,
            project_id=project_id,
            status=status,
            trace_id=trace_id,
        )
        return self._reference_from_event(event, project_id, task_type)

    def get_task_sync(self, db: Session, task_id: str) -> TaskReference:
        snapshot = task_event_service.get_task_snapshot_sync(db, str(task_id))
        return TaskReference(
            id=snapshot["task_id"],
            project_id=snapshot.get("project_id") or 0,
            task_type=snapshot.get("task_type") or "unknown",
            status=snapshot.get("status") or "queued",
            progress=snapshot.get("progress") or 0,
            trace_id=snapshot.get("trace_id"),
            celery_task_id=snapshot.get("celery_task_id"),
            current_step=snapshot.get("current_step"),
            current_frame_id=snapshot.get("current_frame_id"),
        )

    def start_task_sync(
        self,
        db: Session,
        task_id: str,
        step_name: str | None = None,
        *,
        allow_restart: bool = False,
    ) -> None:
        snapshot = task_event_service.get_task_snapshot_sync(db, str(task_id))
        if snapshot.get("status") in TERMINAL_STATUSES and not allow_restart:
            raise ValueError(f"generation task is terminal: {task_id} status={snapshot.get('status')}")
        task_event_service.emit_event_sync(
            db=db,
            task_id=str(task_id),
            task_domain="generation",
            task_type=snapshot.get("task_type") or "unknown",
            event_type="task_started",
            status="running",
            progress=snapshot.get("progress") or 0,
            project_id=snapshot.get("project_id"),
            trace_id=snapshot.get("trace_id"),
            current_step=step_name,
        )

    def update_task_sync(
        self,
        db: Session,
        task_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        current_step: str | None = None,
        current_frame_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        snapshot = task_event_service.get_task_snapshot_sync(db, str(task_id))
        event_type = "task_progress"
        if status == "succeeded":
            event_type = "task_succeeded"
        elif status == "failed":
            event_type = "task_failed"
        elif status == "cancelled":
            event_type = "task_cancelled"
        task_event_service.emit_event_sync(
            db=db,
            task_id=str(task_id),
            task_domain="generation",
            task_type=snapshot.get("task_type") or "unknown",
            event_type=event_type,
            status=status or snapshot.get("status"),
            progress=progress,
            project_id=snapshot.get("project_id"),
            trace_id=snapshot.get("trace_id"),
            current_step=current_step,
            current_frame_id=current_frame_id,
            error={"code": error_code, "message": error_message} if (error_code or error_message) else None,
        )

    def start_step_sync(
        self,
        db: Session,
        task_id: str,
        step_name: str,
        *,
        progress: int = 0,
        frame_id: int | None = None,
        input_snapshot: dict[str, Any] | None = None,
    ) -> StepReference:
        snapshot = task_event_service.get_task_snapshot_sync(db, str(task_id))
        if snapshot.get("status") in TERMINAL_STATUSES:
            raise ValueError(f"generation task is terminal: {task_id} status={snapshot.get('status')}")
        step = {
            "step_key": step_name,
            "frame_id": frame_id,
            "status": "running",
            "progress": progress,
            "input_snapshot": input_snapshot,
        }
        task_event_service.emit_event_sync(
            db=db,
            task_id=str(task_id),
            task_domain="generation",
            task_type=snapshot.get("task_type") or "unknown",
            event_type="step_started",
            status="running",
            progress=progress,
            project_id=snapshot.get("project_id"),
            trace_id=snapshot.get("trace_id"),
            current_step=step_name,
            current_frame_id=frame_id,
            step=step,
        )
        return StepReference(str(task_id), step_name, frame_id, progress, input_snapshot)

    def finish_step_sync(
        self,
        db: Session,
        step: StepReference | None,
        *,
        status: str = "succeeded",
        progress: int | None = None,
        output_snapshot: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if step is None:
            return
        snapshot = task_event_service.get_task_snapshot_sync(db, step.task_id)
        task_event_service.emit_event_sync(
            db=db,
            task_id=step.task_id,
            task_domain="generation",
            task_type=snapshot.get("task_type") or "unknown",
            event_type="step_finished",
            status=snapshot.get("status"),
            progress=progress,
            project_id=snapshot.get("project_id"),
            trace_id=snapshot.get("trace_id"),
            current_step=step.step_name,
            current_frame_id=step.frame_id,
            step={
                "step_key": step.step_name,
                "frame_id": step.frame_id,
                "status": status,
                "progress": progress if progress is not None else step.progress,
                "input_snapshot": step.input_snapshot,
                "output_snapshot": output_snapshot,
                "error_message": error_message,
            },
        )

    @staticmethod
    def _reference_from_event(event: dict, project_id: int, task_type: str) -> TaskReference:
        return TaskReference(
            id=event["task_id"],
            project_id=project_id,
            task_type=task_type,
            status=event["status"],
            progress=event["progress"],
            trace_id=event["trace_id"],
        )


generation_task_service = GenerationTaskService()
