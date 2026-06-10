from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy import desc, select

from backend.v1.app.push.model.message_model import PushMessage


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "completed"}


@dataclass
class TaskEvent:
    task_id: str
    task_domain: str
    task_type: str
    event_type: str
    status: str | None = None
    progress: int | None = None
    project_id: int | None = None
    asset_id: int | None = None
    user_id: int | None = None
    trace_id: str | None = None
    celery_task_id: str | None = None
    current_step: str | None = None
    current_frame_id: int | None = None
    step: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: str | None = None


class TaskEventService:
    @staticmethod
    def _event_field(event: TaskEvent | dict[str, Any], field: str, default: Any = None) -> Any:
        if isinstance(event, dict):
            return event.get(field, default)
        return getattr(event, field, default)

    def generate_task_id(self, task_domain: str) -> str:
        prefix = "merge" if task_domain == "merge" else "gen"
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def build_event_payload(
        self,
        *,
        task_id: str,
        task_domain: str,
        task_type: str,
        event_type: str,
        trace_id: str | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
        asset_id: int | None = None,
        celery_task_id: str | None = None,
        status: str | None = None,
        progress: int | None = None,
        current_step: str | None = None,
        current_frame_id: int | None = None,
        step: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_type": event_type,
            "task_id": task_id,
            "task_domain": task_domain,
            "task_type": task_type,
            "trace_id": trace_id,
            "user_id": user_id,
            "project_id": project_id,
            "asset_id": asset_id,
            "celery_task_id": celery_task_id,
            "status": status,
            "progress": self._clamp_progress(progress),
            "current_step": current_step,
            "current_frame_id": current_frame_id,
            "step": step,
            "result": result,
            "error": error,
        }

    def create_task_sync(
        self,
        *,
        db: Any,
        user_id: int | None = None,
        task_domain: str,
        task_type: str,
        project_id: int | None = None,
        asset_id: int | None = None,
        status: str = "queued",
        trace_id: str | None = None,
        task_id: str | None = None,
        celery_task_id: str | None = None,
        extra: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from backend.framework.trace import get_trace_id
        from backend.v1.app.push.dao.message_dao import message_dao
        from backend.v1.app.push.dto.message_schema import PushMessageCreate

        resolved_task_id = task_id or self.generate_task_id(task_domain)
        resolved_trace_id = trace_id or get_trace_id()
        payload = self.build_event_payload(
            task_id=resolved_task_id,
            task_domain=task_domain,
            task_type=task_type,
            event_type="task_created",
            trace_id=resolved_trace_id,
            user_id=user_id,
            project_id=project_id,
            asset_id=asset_id,
            celery_task_id=celery_task_id,
            status=status,
            progress=0,
            result=extra,
        )
        message_id = uuid.uuid4().hex
        message_dao.create_message_sync(
            db,
            PushMessageCreate(
                user_id=user_id or 0,
                message_type="task_event",
                title="Task created",
                content=payload,
                level="info",
                trace_id=resolved_trace_id,
                business_type="task",
                task_id=resolved_task_id,
                task_domain=task_domain,
                task_type=task_type,
                project_id=project_id,
                asset_id=asset_id,
                event_type="task_created",
                status=status,
                progress=0,
            ),
            message_id,
            commit=commit,
        )
        return {
            "task_id": resolved_task_id,
            "trace_id": resolved_trace_id,
            "status": status,
            "progress": 0,
        }

    def emit_event_sync(
        self,
        *,
        db: Any,
        task_id: str,
        task_domain: str,
        task_type: str,
        event_type: str,
        status: str | None = None,
        progress: int | None = None,
        project_id: int | None = None,
        asset_id: int | None = None,
        user_id: int | None = None,
        trace_id: str | None = None,
        celery_task_id: str | None = None,
        current_step: str | None = None,
        current_frame_id: int | None = None,
        step: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        from backend.framework.trace import get_trace_id
        from backend.v1.app.push.dao.message_dao import message_dao
        from backend.v1.app.push.dto.message_schema import PushMessageCreate

        resolved_trace_id = trace_id or get_trace_id()
        clamped_progress = self._clamp_progress(progress)
        payload = self.build_event_payload(
            task_id=task_id,
            task_domain=task_domain,
            task_type=task_type,
            event_type=event_type,
            trace_id=resolved_trace_id,
            user_id=user_id,
            project_id=project_id,
            asset_id=asset_id,
            celery_task_id=celery_task_id,
            status=status,
            progress=clamped_progress,
            current_step=current_step,
            current_frame_id=current_frame_id,
            step=step,
            result=result,
            error=error,
        )
        message_id = uuid.uuid4().hex
        message_dao.create_message_sync(
            db,
            PushMessageCreate(
                user_id=user_id or 0,
                message_type="task_event",
                title="Task event",
                content=payload,
                level="error" if event_type in {"task_failed"} else "info",
                trace_id=resolved_trace_id,
                business_type="task",
                task_id=task_id,
                task_domain=task_domain,
                task_type=task_type,
                project_id=project_id,
                asset_id=asset_id,
                event_type=event_type,
                status=status,
                progress=clamped_progress,
            ),
            message_id,
            commit=commit,
        )
        return payload

    def events_from_rows(self, rows: list[Any]) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for row in rows:
            content = row.content or {}
            created_at = row.created_at.isoformat() if getattr(row, "created_at", None) else None
            error = content.get("error")
            if error is None and content.get("error_message"):
                error = {"message": content.get("error_message")}
            events.append(
                TaskEvent(
                    task_id=row.task_id or content.get("task_id"),
                    task_domain=row.task_domain or content.get("task_domain"),
                    task_type=row.task_type or content.get("task_type"),
                    event_type=row.event_type or content.get("event_type"),
                    status=row.status if row.status is not None else content.get("status"),
                    progress=row.progress if row.progress is not None else content.get("progress"),
                    project_id=row.project_id if row.project_id is not None else content.get("project_id"),
                    asset_id=row.asset_id if row.asset_id is not None else content.get("asset_id"),
                    user_id=content.get("user_id"),
                    trace_id=row.trace_id or content.get("trace_id"),
                    celery_task_id=getattr(row, "celery_task_id", None) or content.get("celery_task_id"),
                    current_step=content.get("current_step"),
                    current_frame_id=content.get("current_frame_id"),
                    step=content.get("step"),
                    result=content.get("result"),
                    error=error,
                    created_at=created_at,
                )
            )
        return events

    def get_task_events_sync(self, db: Any, task_id: str) -> list[TaskEvent]:
        rows = (
            db.query(PushMessage)
            .filter(PushMessage.message_type == "task_event", PushMessage.task_id == task_id)
            .order_by(PushMessage.created_at.asc(), PushMessage.id.asc())
            .all()
        )
        return self.events_from_rows(rows)

    def get_task_snapshot_sync(self, db: Any, task_id: str) -> dict[str, Any]:
        return self.aggregate_snapshot(self.get_task_events_sync(db, task_id))

    def get_task_steps_sync(self, db: Any, task_id: str) -> list[dict[str, Any]]:
        return self.aggregate_steps(self.get_task_events_sync(db, task_id))

    def get_latest_project_task_sync(self, db: Any, project_id: int) -> dict[str, Any]:
        row = (
            db.query(PushMessage.task_id)
            .filter(PushMessage.message_type == "task_event", PushMessage.project_id == project_id)
            .order_by(desc(PushMessage.created_at), desc(PushMessage.id))
            .first()
        )
        if not row:
            raise ValueError("task events not found")
        task_id = row[0] if isinstance(row, tuple) else row.task_id
        return self.get_task_snapshot_sync(db, task_id)

    async def get_task_events(self, db: Any, task_id: str) -> list[TaskEvent]:
        result = await db.execute(
            select(PushMessage)
            .where(PushMessage.message_type == "task_event", PushMessage.task_id == task_id)
            .order_by(PushMessage.created_at.asc(), PushMessage.id.asc())
        )
        return self.events_from_rows(result.scalars().all())

    async def get_task_snapshot(self, db: Any, task_id: str) -> dict[str, Any]:
        return self.aggregate_snapshot(await self.get_task_events(db, task_id))

    async def get_task_steps(self, db: Any, task_id: str) -> list[dict[str, Any]]:
        return self.aggregate_steps(await self.get_task_events(db, task_id))

    def aggregate_snapshot(self, events: list[TaskEvent]) -> dict[str, Any]:
        if not events:
            raise ValueError("task events not found")

        ordered = list(events)
        first = ordered[0]
        latest = ordered[-1]
        started = next((event for event in ordered if event.event_type == "task_started"), None)
        finished = next((event for event in ordered if event.status in TERMINAL_STATUSES), None)
        latest_error = next((event for event in reversed(ordered) if event.error), None)
        latest_result = next((event for event in reversed(ordered) if event.result), None)

        return {
            "id": latest.task_id,
            "task_id": latest.task_id,
            "project_id": latest.project_id,
            "asset_id": latest.asset_id,
            "celery_task_id": latest.celery_task_id,
            "task_domain": latest.task_domain,
            "task_type": latest.task_type,
            "status": latest.status,
            "progress": self._clamp_progress(latest.progress),
            "current_step": latest.current_step,
            "current_frame_id": latest.current_frame_id,
            "error_code": (latest_error.error or {}).get("code") if latest_error else None,
            "error_message": (latest_error.error or {}).get("message") if latest_error else None,
            "result": latest_result.result if latest_result else None,
            "trace_id": latest.trace_id,
            "created_at": first.created_at,
            "started_at": started.created_at if started else None,
            "finished_at": finished.created_at if finished else None,
        }

    def aggregate_steps(self, events: list[TaskEvent] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, int | None], dict[str, Any]] = {}

        for event in events:
            step = self._event_field(event, "step")
            if not step:
                continue
            step_key = step.get("step_key")
            if not step_key:
                continue
            frame_id = step.get("frame_id")
            key = (step_key, frame_id)
            current = grouped.setdefault(
                key,
                {
                    "step_name": step_key,
                    "frame_id": frame_id,
                    "status": None,
                    "progress": 0,
                    "input_snapshot": None,
                    "output_snapshot": None,
                    "error_message": None,
                    "started_at": None,
                    "finished_at": None,
                },
            )
            if current["started_at"] is None:
                current["started_at"] = self._event_field(event, "created_at")
            current["status"] = step.get("status", self._event_field(event, "status"))
            current["progress"] = self._clamp_progress(step.get("progress", self._event_field(event, "progress")))
            current["input_snapshot"] = step.get("input_snapshot", current["input_snapshot"])
            current["output_snapshot"] = step.get("output_snapshot", current["output_snapshot"])
            current["error_message"] = step.get("error_message", current["error_message"])
            if current["status"] in TERMINAL_STATUSES or self._event_field(event, "event_type") == "step_finished":
                current["finished_at"] = self._event_field(event, "created_at")

        return list(grouped.values())

    @staticmethod
    def _clamp_progress(progress: int | None) -> int | None:
        if progress is None:
            return None
        return max(0, min(100, int(progress)))


task_event_service = TaskEventService()
