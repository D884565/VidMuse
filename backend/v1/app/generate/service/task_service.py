"""Generation task progress service."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.v1.app.models.generation_task import GenerationTask, GenerationTaskStep
from backend.v1.app.models.project import Project


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


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
    ) -> GenerationTask:
        task = GenerationTask(
            project_id=project_id,
            task_type=task_type,
            status=status,
            progress=0,
            trace_id=trace_id or uuid.uuid4().hex,
        )
        db.add(task)
        if commit:
            await db.commit()
            await db.refresh(task)
        else:
            # 调用方需要原子提交时，只 flush 出 id，不提前提交事务。
            await db.flush()
        return task

    async def set_celery_task_id(self, db: AsyncSession, task_id: int, celery_task_id: str) -> None:
        task = await self.get_task_model(db, task_id)
        task.celery_task_id = celery_task_id
        await db.commit()

    async def get_task_model(self, db: AsyncSession, task_id: int) -> GenerationTask:
        result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"generation task not found: {task_id}")
        return task

    async def get_task(self, db: AsyncSession, task_id: int, user_id: int | None = None) -> dict:
        task = await self.get_task_model(db, task_id)
        if user_id is not None:
            await self._assert_task_owner(db, task, user_id)
        return self._task_to_dict(task)

    async def list_steps(self, db: AsyncSession, task_id: int, user_id: int | None = None) -> list[dict]:
        task = await self.get_task_model(db, task_id)
        if user_id is not None:
            await self._assert_task_owner(db, task, user_id)
        result = await db.execute(
            select(GenerationTaskStep)
            .where(GenerationTaskStep.task_id == task_id)
            .order_by(GenerationTaskStep.id.asc())
        )
        return [self._step_to_dict(step) for step in result.scalars().all()]

    async def _assert_task_owner(self, db: AsyncSession, task: GenerationTask, user_id: int) -> None:
        result = await db.execute(select(Project.user_id).where(Project.id == task.project_id))
        owner_id = result.scalar_one_or_none()
        if owner_id != user_id:
            raise PermissionError("forbidden")

    def create_task_sync(
        self,
        db: Session,
        project_id: int,
        task_type: str,
        *,
        status: str = "queued",
        trace_id: str | None = None,
    ) -> GenerationTask:
        task = GenerationTask(
            project_id=project_id,
            task_type=task_type,
            status=status,
            progress=0,
            trace_id=trace_id or uuid.uuid4().hex,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def get_task_sync(self, db: Session, task_id: int) -> GenerationTask:
        task = db.get(GenerationTask, task_id)
        if not task:
            raise ValueError(f"generation task not found: {task_id}")
        return task

    def start_task_sync(
        self,
        db: Session,
        task_id: int,
        step_name: str | None = None,
        *,
        allow_restart: bool = False,
    ) -> None:
        task = self.get_task_sync(db, task_id)
        if task.status in TERMINAL_STATUSES and not allow_restart:
            raise ValueError(f"generation task is terminal: {task_id} status={task.status}")
        task.status = "running"
        task.started_at = task.started_at or datetime.utcnow()
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        if step_name:
            task.current_step = step_name
        db.commit()

    def update_task_sync(
        self,
        db: Session,
        task_id: int,
        *,
        status: str | None = None,
        progress: int | None = None,
        current_step: str | None = None,
        current_frame_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        task = self.get_task_sync(db, task_id)
        if status is not None:
            task.status = status
            if status in TERMINAL_STATUSES:
                task.finished_at = datetime.utcnow()
        if progress is not None:
            task.progress = max(0, min(100, int(progress)))
        if current_step is not None:
            task.current_step = current_step
        if current_frame_id is not None:
            task.current_frame_id = current_frame_id
        if error_code is not None:
            task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message
        db.commit()

    def start_step_sync(
        self,
        db: Session,
        task_id: int,
        step_name: str,
        *,
        progress: int = 0,
        frame_id: int | None = None,
        input_snapshot: dict[str, Any] | None = None,
    ) -> GenerationTaskStep | None:
        task = self.get_task_sync(db, task_id)
        if task.status in TERMINAL_STATUSES:
            raise ValueError(f"generation task is terminal: {task_id} status={task.status}")
        step = GenerationTaskStep(
            task_id=task_id,
            step_name=step_name,
            frame_id=frame_id,
            status="running",
            progress=progress,
            input_snapshot=input_snapshot,
            started_at=datetime.utcnow(),
        )
        db.add(step)
        task.status = "running"
        task.started_at = task.started_at or datetime.utcnow()
        task.current_step = step_name
        task.current_frame_id = frame_id
        task.progress = max(task.progress or 0, progress)
        db.commit()
        db.refresh(step)
        return step

    def finish_step_sync(
        self,
        db: Session,
        step: GenerationTaskStep | int | None,
        *,
        status: str = "succeeded",
        progress: int | None = None,
        output_snapshot: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if step is None:
            return
        step_model = db.get(GenerationTaskStep, step) if isinstance(step, int) else step
        if not step_model:
            raise ValueError(f"generation task step not found: {step}")
        step_model.status = status
        if progress is not None:
            step_model.progress = max(0, min(100, int(progress)))
        if output_snapshot is not None:
            step_model.output_snapshot = output_snapshot
        if error_message is not None:
            step_model.error_message = error_message
        step_model.finished_at = datetime.utcnow()
        db.commit()

    def _task_to_dict(self, task: GenerationTask) -> dict:
        return {
            "id": task.id,
            "project_id": task.project_id,
            "celery_task_id": task.celery_task_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "current_step": task.current_step,
            "current_frame_id": task.current_frame_id,
            "retry_count": task.retry_count,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "trace_id": task.trace_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        }

    def _step_to_dict(self, step: GenerationTaskStep) -> dict:
        return {
            "id": step.id,
            "task_id": step.task_id,
            "step_name": step.step_name,
            "frame_id": step.frame_id,
            "status": step.status,
            "progress": step.progress,
            "input_snapshot": step.input_snapshot,
            "output_snapshot": step.output_snapshot,
            "error_message": step.error_message,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "finished_at": step.finished_at.isoformat() if step.finished_at else None,
        }


generation_task_service = GenerationTaskService()
