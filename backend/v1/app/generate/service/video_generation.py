"""视频生成调度服务"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.asset import Asset
from backend.v1.app.generate.temp.celery_app import celery_app
from backend.v1.app.generate.service.task_service import generation_task_service


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


class VideoGenerationService:
    """视频生成调度服务（编排剧本→TTS→图片→合成→入库）"""

    async def submit_generation_task(
        self,
        db: AsyncSession,
        project_id: int,
    ) -> dict:
        """
        提交视频生成异步任务。

        1. 校验项目状态和帧数据
        2. 更新状态为 processing
        3. 发送 Celery 任务
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        if project.status in ("script_generating", "processing", "render_queued", "rendering"):
            return {
                "project_id": project_id,
                "frames_count": 0,
                "status": project.status,
                "message": "generation already in progress",
            }
        if project.status not in ("script_ready", "completed", "failed"):
            raise ValueError(f"当前状态不允许生成: {project.status}")

        # 检查是否有帧数据
        frame_result = await db.execute(
            select(Frame).where(Frame.project_id == project_id)
        )
        frames = frame_result.scalars().all()
        if not frames:
            raise ValueError("请先生成剧本（无帧数据）")

        task = await generation_task_service.create_task(db, project_id, "render", status="queued")

        # 更新状态，避免前端重复提交渲染任务。
        project.status = "render_queued"
        await db.commit()

        # 异步发送 Celery 任务
        async_result = celery_app.send_task(
            "generate_video_task",
            args=[project_id, task.id],
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
        """查询项目详情（含帧和素材），供前端轮询"""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 获取帧列表
        frame_result = await db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        )
        frames = frame_result.scalars().all()

        # 获取用户资产（assets 是用户级别，通过 user_id 关联）
        assets = []
        if project.user_id:
            asset_result = await db.execute(
                select(Asset).where(Asset.user_id == project.user_id)
            )
            assets = asset_result.scalars().all()

        # 查找视频资产ID（用于 Merge 服务）
        video_asset_id = None
        if project.video_output_url:
            video_asset_result = await db.execute(
                select(Asset.id).where(
                    Asset.url == project.video_output_url,
                    Asset.type == 2,
                ).limit(1)
            )
            video_asset_id_row = video_asset_result.scalar_one_or_none()
            if video_asset_id_row:
                video_asset_id = video_asset_id_row

        return {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "status_code": STATUS_TO_INT.get(project.status, 0),
            "video_url": project.video_output_url,
            "video_asset_id": video_asset_id,
            "audio_url": project.audio_url,
            "frames": [
                {
                    "id": f.id,
                    "sequence": f.sequence,
                    "scene_type": f.scene_type,
                    "description": f.description,
                    "prompt": f.prompt,
                    "image_url": f.image_url,
                    "audio_url": f.audio_url,
                    "duration": float(f.duration),
                    "status": f.status,
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
                }
                for a in assets
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
        """Celery Worker 回调：更新视频生成结果"""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.video_output_url = video_url
            project.status = status
            await db.commit()


video_generation_service = VideoGenerationService()
