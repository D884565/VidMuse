import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from backend.v1.app.models.generation_task import GenerationTask
from backend.v1.app.models.generation_frame_progress import GenerationFrameProgress


class TaskTrackerDAO:
    """任务追踪数据访问层。"""

    def generate_task_id(self) -> str:
        """生成唯一任务ID。"""
        return f"gen_{uuid.uuid4().hex[:16]}"

    def create_task(
        self,
        db: Session,
        project_id: int,
        task_type: str,
        trigger_source: str = "manual",
        task_id: Optional[str] = None,
    ) -> GenerationTask:
        """创建生成任务。"""
        if task_id:
            existing = self.get_task(db, task_id)
            if existing:
                return existing

        task = GenerationTask(
            task_id=task_id or self.generate_task_id(),
            project_id=project_id,
            task_type=task_type,
            status="queued",
            trigger_source=trigger_source,
        )
        db.add(task)
        db.flush()
        return task

    def get_task(self, db: Session, task_id: str) -> Optional[GenerationTask]:
        """获取任务。"""
        return db.execute(
            select(GenerationTask).where(GenerationTask.task_id == task_id)
        ).scalar_one_or_none()

    def get_latest_task(self, db: Session, project_id: int) -> Optional[GenerationTask]:
        """获取项目最新的任务。"""
        return db.execute(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def update_task(
        self,
        db: Session,
        task_id: str,
        **kwargs,
    ) -> None:
        """更新任务字段。"""
        db.execute(
            update(GenerationTask)
            .where(GenerationTask.task_id == task_id)
            .values(**kwargs)
        )
        db.flush()

    def start_task(self, db: Session, task_id: str, stage: str) -> None:
        """标记任务开始。"""
        self.update_task(
            db, task_id,
            status="running",
            current_stage=stage,
            started_at=datetime.utcnow(),
        )

    def complete_task(self, db: Session, task_id: str) -> None:
        """标记任务完成。"""
        self.update_task(
            db, task_id,
            status="succeeded",
            progress=100,
            finished_at=datetime.utcnow(),
        )

    def fail_task(self, db: Session, task_id: str, error_code: str, error_message: str) -> None:
        """标记任务失败。"""
        self.update_task(
            db, task_id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
            finished_at=datetime.utcnow(),
        )

    def init_frame_progress(
        self,
        db: Session,
        task_id: str,
        project_id: int,
        frame_ids: list[int],
        stage: str,
    ) -> None:
        """批量初始化帧进度记录。"""
        if not frame_ids:
            return

        rows = [
            {
                "task_id": task_id,
                "project_id": project_id,
                "frame_id": frame_id,
                "stage": stage,
                "status": "pending",
                "attempt_count": 0,
                "error_message": None,
                "result_url": None,
                "started_at": None,
                "finished_at": None,
            }
            for frame_id in frame_ids
        ]
        statement = mysql_insert(GenerationFrameProgress).values(rows)
        statement = statement.on_duplicate_key_update(
            project_id=statement.inserted.project_id,
            status="pending",
            error_message=None,
            result_url=None,
            started_at=None,
            finished_at=None,
        )
        db.execute(statement)
        db.flush()

    def update_frame_status(
        self,
        db: Session,
        task_id: str,
        frame_id: int,
        stage: str,
        status: str,
        error_message: Optional[str] = None,
        result_url: Optional[str] = None,
    ) -> None:
        """更新帧状态。"""
        progress = db.execute(
            select(GenerationFrameProgress).where(
                GenerationFrameProgress.task_id == task_id,
                GenerationFrameProgress.frame_id == frame_id,
                GenerationFrameProgress.stage == stage,
            )
        ).scalar_one_or_none()

        if not progress:
            return

        progress.status = status
        progress.attempt_count += 1

        if status == "running":
            progress.started_at = datetime.utcnow()
        elif status in ("succeeded", "failed"):
            progress.finished_at = datetime.utcnow()

        if error_message:
            progress.error_message = error_message
        if result_url:
            progress.result_url = result_url

        db.flush()

    def get_pending_frames(self, db: Session, task_id: str, stage: str) -> list[int]:
        """获取待处理的帧ID列表。"""
        results = db.execute(
            select(GenerationFrameProgress.frame_id).where(
                GenerationFrameProgress.task_id == task_id,
                GenerationFrameProgress.stage == stage,
                GenerationFrameProgress.status == "pending",
            )
        ).scalars().all()
        return list(results)

    def get_failed_frames(self, db: Session, task_id: str, stage: str) -> list[int]:
        """获取失败的帧ID列表。"""
        results = db.execute(
            select(GenerationFrameProgress.frame_id).where(
                GenerationFrameProgress.task_id == task_id,
                GenerationFrameProgress.stage == stage,
                GenerationFrameProgress.status == "failed",
            )
        ).scalars().all()
        return list(results)

    def get_frame_summary(self, db: Session, task_id: str, stage: str) -> dict:
        """获取帧状态汇总。"""
        from sqlalchemy import func as sql_func

        results = db.execute(
            select(
                GenerationFrameProgress.status,
                sql_func.count(GenerationFrameProgress.id).label("count"),
            )
            .where(
                GenerationFrameProgress.task_id == task_id,
                GenerationFrameProgress.stage == stage,
            )
            .group_by(GenerationFrameProgress.status)
        ).all()

        summary = {"total": 0, "pending": 0, "running": 0, "succeeded": 0, "failed": 0}
        for status, count in results:
            summary[status] = count
            summary["total"] += count

        return summary

    def get_frame_progress_list(self, db: Session, task_id: str, stage: str) -> list[GenerationFrameProgress]:
        """获取帧进度列表。"""
        return list(db.execute(
            select(GenerationFrameProgress)
            .where(
                GenerationFrameProgress.task_id == task_id,
                GenerationFrameProgress.stage == stage,
            )
            .order_by(GenerationFrameProgress.frame_id)
        ).scalars().all())


task_tracker_dao = TaskTrackerDAO()
