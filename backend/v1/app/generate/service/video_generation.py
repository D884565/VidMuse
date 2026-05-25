"""视频生成调度服务"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script
from backend.v1.app.models.asset import Asset
from backend.v1.app.generate.temp.celery_app import celery_app



class VideoGenerationService:
    """视频生成调度服务（编排剧本→TTS→图片→合成→入库）"""

    async def submit_generation_task(
        self,
        db: AsyncSession,
        project_id: int,
    ) -> dict:
        """
        提交视频生成异步任务。

        1. 校验项目状态
        2. 更新状态为 processing
        3. 发送 Celery 任务
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        if project.status not in ("script_ready", "draft"):
            raise ValueError(f"当前状态不允许生成: {project.status}")

        # 查找最新剧本
        script_result = await db.execute(
            select(Script).where(Script.project_id == project_id).order_by(Script.id.desc())
        )
        script = script_result.scalars().first()
        if not script:
            raise ValueError("请先生成剧本")

        # 更新状态
        project.status = "processing"
        await db.commit()

        # 异步发送 Celery 任务
        celery_app.send_task(
            "generate_video_task",
            args=[project_id, script.id],
        )

        return {
            "project_id": project_id,
            "script_id": script.id,
            "status": "processing",
        }

    async def get_project_detail(self, db: AsyncSession, project_id: int) -> dict:
        """查询项目详情（含剧本和素材），供前端轮询"""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 获取剧本
        script_result = await db.execute(
            select(Script).where(Script.project_id == project_id).order_by(Script.id.desc())
        )
        script = script_result.scalars().first()

        # 获取用户资产（assets 是用户级别，通过 user_id 关联）
        assets = []
        if project.user_id:
            asset_result = await db.execute(
                select(Asset).where(Asset.user_id == project.user_id)
            )
            assets = asset_result.scalars().all()

        return {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "video_url": project.video_output_url,
            "script": {"id": script.id, "content": script.content} if script else None,
            "assets": [
                {
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
