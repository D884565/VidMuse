from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.generate.service.generateUtils.task_tracker import generation_task_tracker


@dataclass
class ResumePoint:
    """恢复点信息。"""
    stage: str  # 从哪个阶段开始: image, video, start
    task_id: Optional[str]  # 上一个任务ID
    frames_to_retry: list[int]  # 需要重试的帧ID列表
    trigger_source: str  # 触发来源: resume, user_revision


class RetryCoordinator:
    """重试协调器 - 决定从哪里恢复。"""

    def determine_resume_point(self, db: Session, project_id: int) -> ResumePoint:
        """
        分析项目状态，确定恢复点。

        检查顺序：
        1. 获取项目最新任务
        2. 检查任务状态
        3. 检查帧级进度
        4. 返回恢复点
        """
        task = generation_task_tracker.get_latest_task(db, project_id)

        if not task:
            return ResumePoint(stage="start", task_id=None, frames_to_retry=[], trigger_source="manual")

        task_id = task["task_id"]
        status = task["status"]
        current_stage = task["current_stage"]

        # 任务成功或取消，不需要重试
        if status in ("succeeded", "cancelled"):
            return ResumePoint(stage="start", task_id=None, frames_to_retry=[], trigger_source="manual")

        # 任务失败，检查哪个阶段失败
        if status == "failed":
            # 检查图片阶段
            if current_stage == "image":
                failed_frames = generation_task_tracker.get_failed_frames(db, task_id, "image")
                return ResumePoint(
                    stage="image",
                    task_id=task_id,
                    frames_to_retry=failed_frames,
                    trigger_source="resume",
                )

            # 检查视频阶段
            if current_stage == "video":
                failed_frames = generation_task_tracker.get_failed_frames(db, task_id, "video")
                return ResumePoint(
                    stage="video",
                    task_id=task_id,
                    frames_to_retry=failed_frames,
                    trigger_source="resume",
                )

        # 任务运行中，可能是超时或中断
        if status == "running":
            if current_stage == "image":
                pending_frames = generation_task_tracker.get_pending_frames(db, task_id, "image")
                failed_frames = generation_task_tracker.get_failed_frames(db, task_id, "image")
                return ResumePoint(
                    stage="image",
                    task_id=task_id,
                    frames_to_retry=pending_frames + failed_frames,
                    trigger_source="resume",
                )

            if current_stage == "video":
                pending_frames = generation_task_tracker.get_pending_frames(db, task_id, "video")
                failed_frames = generation_task_tracker.get_failed_frames(db, task_id, "video")
                return ResumePoint(
                    stage="video",
                    task_id=task_id,
                    frames_to_retry=pending_frames + failed_frames,
                    trigger_source="resume",
                )

        # 默认从头开始
        return ResumePoint(stage="start", task_id=None, frames_to_retry=[], trigger_source="manual")

    def prepare_retry(
        self,
        db: Session,
        project_id: int,
        stage: Optional[str] = None,
        frame_ids: Optional[list[int]] = None,
    ) -> tuple[str, list[int]]:
        """
        准备重试：创建新任务，返回 (task_id, frames_to_retry)。

        Args:
            db: 数据库会话
            project_id: 项目ID
            stage: 指定阶段（可选）
            frame_ids: 指定帧ID（可选，用于用户修改单帧）
        """
        resume = self.determine_resume_point(db, project_id)

        # 确定要重试的阶段
        retry_stage = stage or resume.stage

        # 确定要重试的帧
        if frame_ids:
            # 用户指定了帧（用户修改场景）
            frames_to_retry = frame_ids
            trigger_source = "user_revision"
        elif resume.frames_to_retry:
            # 从断点恢复（失败重试场景）
            frames_to_retry = resume.frames_to_retry
            trigger_source = "resume"
        else:
            # 全新开始
            frames_to_retry = []
            trigger_source = "manual"

        # 创建新任务
        task_type = f"{retry_stage}_retry" if trigger_source == "resume" else retry_stage
        task_id = generation_task_tracker.create_task(db, project_id, task_type, trigger_source)

        return task_id, frames_to_retry

    def get_generation_status(self, db: Session, project_id: int) -> dict:
        """获取项目生成状态。"""
        task = generation_task_tracker.get_latest_task(db, project_id)

        if not task:
            return {
                "task_id": None,
                "status": "idle",
                "current_stage": None,
                "progress": 0,
                "stages": {},
                "error": None,
            }

        task_id = task["task_id"]

        # 获取各阶段状态
        stages = {}
        for stage in ["tts", "image", "video", "audio_mix", "bgm_mix", "output"]:
            if stage in ("image", "video"):
                summary = generation_task_tracker.get_frame_summary(db, task_id, stage)
                stages[stage] = {
                    "status": "succeeded" if summary["failed"] == 0 and summary["succeeded"] == summary["total"] else "pending",
                    "progress": int(summary["succeeded"] / summary["total"] * 100) if summary["total"] > 0 else 0,
                    "frame_summary": summary,
                }
            else:
                # 其他阶段根据当前进度推断
                stages[stage] = {"status": "pending", "progress": 0}

        return {
            "task_id": task_id,
            "status": task["status"],
            "current_stage": task["current_stage"],
            "progress": task["progress"],
            "stages": stages,
            "error": {
                "code": task["error_code"],
                "message": task["error_message"],
            } if task["error_code"] else None,
        }


retry_coordinator = RetryCoordinator()
