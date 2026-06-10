from typing import Optional

from sqlalchemy.orm import Session

from backend.v1.app.generate.dao.task_tracker_dao import task_tracker_dao


class GenerationTaskTracker:
    """生成任务追踪器 - 管理任务和帧级进度。"""

    def create_task(
        self,
        db: Session,
        project_id: int,
        task_type: str,
        trigger_source: str = "manual",
        task_id: Optional[str] = None,
    ) -> str:
        """创建新任务，返回 task_id。"""
        task = task_tracker_dao.create_task(db, project_id, task_type, trigger_source, task_id)
        return task.task_id

    def get_task(self, db: Session, task_id: str) -> Optional[dict]:
        """获取任务信息。"""
        task = task_tracker_dao.get_task(db, task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "task_type": task.task_type,
            "status": task.status,
            "current_stage": task.current_stage,
            "progress": task.progress,
            "retry_count": task.retry_count,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "trigger_source": task.trigger_source,
        }

    def get_latest_task(self, db: Session, project_id: int) -> Optional[dict]:
        """获取项目最新任务。"""
        task = task_tracker_dao.get_latest_task(db, project_id)
        if not task:
            return None
        return self.get_task(db, task.task_id)

    def start_task(self, db: Session, task_id: str, stage: str) -> None:
        """标记任务开始。"""
        task_tracker_dao.start_task(db, task_id, stage)

    def update_stage(
        self,
        db: Session,
        task_id: str,
        stage: str,
        progress: int | None = None,
        *,
        status: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """更新当前阶段和进度。"""
        payload = {"current_stage": stage}
        if progress is not None:
            payload["progress"] = progress
        if status is not None:
            payload["status"] = status
        if error_message is not None:
            payload["error_message"] = error_message
        task_tracker_dao.update_task(db, task_id, **payload)

    def complete_task(self, db: Session, task_id: str) -> None:
        """标记任务完成。"""
        task_tracker_dao.complete_task(db, task_id)

    def fail_task(self, db: Session, task_id: str, error_code: str, error_message: str) -> None:
        """标记任务失败。"""
        task_tracker_dao.fail_task(db, task_id, error_code, error_message)

    def init_frame_progress(
        self,
        db: Session,
        task_id: str,
        project_id: int,
        frame_ids: list[int],
        stage: str,
    ) -> None:
        """初始化帧进度记录。"""
        task_tracker_dao.init_frame_progress(db, task_id, project_id, frame_ids, stage)

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
        task_tracker_dao.update_frame_status(db, task_id, frame_id, stage, status, error_message, result_url)

    def get_pending_frames(self, db: Session, task_id: str, stage: str) -> list[int]:
        """获取待处理的帧ID列表。"""
        return task_tracker_dao.get_pending_frames(db, task_id, stage)

    def get_failed_frames(self, db: Session, task_id: str, stage: str) -> list[int]:
        """获取失败的帧ID列表。"""
        return task_tracker_dao.get_failed_frames(db, task_id, stage)

    def get_frame_summary(self, db: Session, task_id: str, stage: str) -> dict:
        """获取帧状态汇总。"""
        return task_tracker_dao.get_frame_summary(db, task_id, stage)

    def get_frame_progress_list(self, db: Session, task_id: str, stage: str) -> list[dict]:
        """获取帧进度详情列表。"""
        progress_list = task_tracker_dao.get_frame_progress_list(db, task_id, stage)
        return [
            {
                "frame_id": p.frame_id,
                "status": p.status,
                "attempt_count": p.attempt_count,
                "error_message": p.error_message,
                "result_url": p.result_url,
            }
            for p in progress_list
        ]


generation_task_tracker = GenerationTaskTracker()
