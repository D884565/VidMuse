"""视频生成调度服务。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.project_asset import ProjectAsset
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.generate.service.task_service import generation_task_service
from backend.v1.app.generate.service.workflow import state as project_workflow_state


STATUS_TO_INT = {
    "draft": 0,
    "script_generating": 2,
    "script_ready": 1,
    "processing": 2,
    "render_queued": 2,
    "rendering": 2,
    "completed": 3,
    "failed": 4,
}

ALLOWED_RENDER_WORKFLOW_STATES = {
    ("script", "awaiting_review"),
    ("image", "confirmed"),
    ("video", "idle"),
    ("video", "failed"),
    ("video", "awaiting_review"),
    ("video", "confirmed"),
    ("completed", "confirmed"),
}


class VideoGenerationService:
    """视频生成调度服务，负责提交渲染任务和返回项目详情。"""

    async def submit_generation_task(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        require_ready_images: bool = True,
        trigger_source: str = "manual_render",
    ) -> dict:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        if project.stage_status == "running":
            return {
                "project_id": project_id,
                "frames_count": 0,
                "status": project.stage_status,
                "task_id": project.last_task_id,
                "message": "generation already in progress",
            }

        current_state = (project.workflow_stage, project.stage_status)

        frame_result = await db.execute(select(Frame).where(Frame.project_id == project_id))
        frames = frame_result.scalars().all()
        if not frames:
            raise ValueError("请先生成脚本（无帧数据）")

        invalid_frames = [
            frame.sequence
            for frame in frames
            if frame.status == 3 or not frame.image_url or not str(frame.image_url).startswith("http")
        ]
        if require_ready_images and invalid_frames:
            raise ValueError(f"存在未成功生成图片的分镜，不能进入视频阶段: {invalid_frames}")
        allowed_states = (
            ALLOWED_RENDER_WORKFLOW_STATES - {("script", "awaiting_review")}
            if require_ready_images
            else ALLOWED_RENDER_WORKFLOW_STATES
        )
        if current_state not in allowed_states:
            raise ValueError(
                f"当前工作流状态不允许生成: {project.workflow_stage}/{project.stage_status}"
            )
        task = await generation_task_service.create_task(db, project_id, "render", status="queued")
        project_workflow_state.mark_project_stage_running(project, "video", task.id)
        await db.commit()

        async_result = celery_app.send_task(
            "generate_video_task",
            args=[project_id, task.id],
            kwargs={"trigger_source": trigger_source},
        )
        await generation_task_service.set_celery_task_id(db, task.id, async_result.id)

        return {
            "project_id": project_id,
            "task_id": task.id,
            "celery_task_id": async_result.id,
            "frames_count": len(frames),
            "status": "render_queued",
        }

    async def get_project_detail(self, db: AsyncSession, project_id: int) -> dict:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        frame_result = await db.execute(
            select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence)
        )
        frames = frame_result.scalars().all()

        asset_items = []
        if project.user_id:
            asset_result = await db.execute(
                select(Asset, ProjectAsset.role)
                .join(ProjectAsset, ProjectAsset.asset_id == Asset.id)
                .where(ProjectAsset.project_id == project_id)
                .order_by(ProjectAsset.id)
            )
            asset_items = list(asset_result.all())

        return {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "status_code": STATUS_TO_INT.get(project.status, 0),
            "workflow_stage": project.workflow_stage,
            "stage_status": project.stage_status,
            "dirty_stage": project.dirty_stage,
            "last_task_id": project.last_task_id,
            "script_confirmed_at": project.script_confirmed_at.isoformat() if project.script_confirmed_at else None,
            "images_confirmed_at": project.images_confirmed_at.isoformat() if project.images_confirmed_at else None,
            "video_confirmed_at": project.video_confirmed_at.isoformat() if project.video_confirmed_at else None,
            "video_url": project.video_output_url,
            "audio_url": project.audio_url,
            "frames": [
                {
                    "id": f.id,
                    "script_id": f.script_id,
                    "sequence": f.sequence,
                    "scene_type": f.scene_type,
                    "description": f.description,
                    "prompt": f.prompt,
                    "narration": f.narration,
                    "subtitle_text": f.subtitle_text,
                    "subtitle_position": f.subtitle_position,
                    "image_prompt": f.image_prompt,
                    "video_prompt": f.video_prompt,
                    "image_url": f.image_url,
                    "audio_url": f.audio_url,
                    "video_url": f.video_url,
                    "duration": float(f.duration),
                    "status": f.status,
                    "dirty": bool(f.dirty),
                    "last_edited_at": f.last_edited_at.isoformat() if f.last_edited_at else None,
                    "error_message": f.error_message,
                    "text_overlay": f.text_overlay,
                    "ai_params": f.ai_params,
                }
                for f in frames
            ],
            "assets": [
                {
                    "id": a.id,
                    "type": a.type,
                    "title": a.title,
                    "url": a.url,
                    "duration": a.duration,
                    "role": role,
                }
                for a, role in asset_items
            ],
            "created_at": project.created_at.isoformat() if project.created_at else "",
            "updated_at": project.updated_at.isoformat() if project.updated_at else "",
        }

    async def update_video_result(
        self,
        db: AsyncSession,
        project_id: int,
        video_url: str,
        status: str = "completed",
    ):
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.video_output_url = video_url
            if status == "completed":
                project_workflow_state.mark_project_completed(project)
            else:
                project_workflow_state.mark_project_stage_failed(project, "video")
            await db.commit()


video_generation_service = VideoGenerationService()
