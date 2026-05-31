"""独立的图片阶段工作流服务：负责批量生成分镜图片。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.stages.image_service import image_generation_service
from backend.v1.app.generate.service.generateUtils.reference_image_utils import extract_reference_images
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.generate.service.workflow.blocks import build_image_stage_blocks, build_progress_block
from backend.v1.app.models.conversation import Conversation
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project


def build_image_stage_message(frames: list[Frame], task_id: int | None = None) -> dict:
    """构建图片阶段完成后的 assistant 消息，包含图片网格和操作按钮。"""
    return {
        "role": "assistant",
        "content": "图片阶段已完成。请检查每个分镜的首帧图，满意后可以确认并生成视频。",
        "message_type": "stage_card",
        "stage": "image",
        "blocks": build_image_stage_blocks(frames),
        "action_type": "GENERATE_IMAGES",
        "task_id": task_id,
        "metadata": {
            "frame_count": len(frames),
            "failed_frame_ids": [frame.id for frame in frames if getattr(frame, "status", None) == 3],
        },
    }


class ImageWorkflowService:
    """图片阶段工作流：创建任务 -> 批量生成图片 -> 写入对话消息。"""

    async def submit_image_task(self, db: AsyncSession, project_id: int) -> dict:
        """提交图片阶段后台任务，避免在 FastAPI async 请求中阻塞生成图片。"""
        project = await self._get_project(db, project_id)
        if project.stage_status == "running" and project.workflow_stage == "image":
            return {
                "project_id": project_id,
                "task_id": project.last_task_id,
                "status": "running",
                "message": "image generation already in progress",
            }

        frames = await self._get_frames(db, project_id)
        if not frames:
            raise ValueError("请先生成剧本，再进入图片阶段")

        task = await generation_task_service.create_task(db, project_id, "image", status="queued")
        project_workflow_state.mark_project_stage_running(project, "image", task.id)
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="我开始生成分镜图片了，完成后会把图片网格发在这里。",
            message_type="progress",
            stage="image",
            blocks=[build_progress_block("image", "running", task.id, "正在生成分镜图片")],
            action_type="GENERATE_IMAGES",
            task_id=task.id,
        ))
        await db.commit()

        async_result = celery_app.send_task("generate_image_task", args=[project_id, task.id])
        await generation_task_service.set_celery_task_id(db, task.id, async_result.id)
        return {
            "project_id": project_id,
            "task_id": task.id,
            "celery_task_id": async_result.id,
            "status": "running",
            "frames_count": len(frames),
        }

    async def generate_images(self, db: AsyncSession, project_id: int) -> dict:
        """为项目的所有分镜生成首帧图片。

        流程：校验分镜存在 -> 创建任务 -> 标记运行中 -> 调用图片生成服务 -> 写入结果消息。
        """
        project = await self._get_project(db, project_id)
        frames = await self._get_frames(db, project_id)
        if not frames:
            raise ValueError("请先生成剧本，再进入图片阶段")

        # 创建任务记录并标记图片阶段为运行中
        task = await generation_task_service.create_task(db, project_id, "image", status="running")
        project_workflow_state.mark_project_stage_running(project, "image", task.id)
        # 写入一条进度消息到对话
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="我开始生成分镜图片了，完成后会把图片网格发在这里。",
            message_type="progress",
            stage="image",
            blocks=[build_progress_block("image", "running", task.id, "正在生成分镜图片")],
            action_type="GENERATE_IMAGES",
            task_id=task.id,
        ))
        await db.commit()

        reference_images = extract_reference_images(project)
        try:
            # 图片阶段只产出 frame.image_url，不进入视频生成，避免提前消耗视频额度。
            frames = image_generation_service.generate_frame_images(
                frames,
                project_id,
                reference_images=reference_images,
            )
            failed = [frame.id for frame in frames if frame.status == 3]
            task.status = "failed" if failed else "succeeded"
            task.progress = 100
            task.current_step = "IMAGE_GENERATED"
            task.finished_at = datetime.utcnow()
            project_workflow_state.mark_project_stage_review(project, "image", task.id)
            # 写入图片阶段完成的消息（包含图片网格和操作按钮）
            message = build_image_stage_message(frames, task.id)
            db.add(Conversation(
                project_id=project_id,
                role=message["role"],
                content=message["content"],
                message_type=message["message_type"],
                stage=message["stage"],
                blocks=message["blocks"],
                action_type=message["action_type"],
                task_id=message["task_id"],
                metadata_=message["metadata"],
            ))
            await db.commit()
            return {
                "project_id": project_id,
                "task_id": task.id,
                "status": project.stage_status,
                "failed_frame_ids": failed,
                "frames_count": len(frames),
            }
        except Exception as exc:
            # 图片生成失败时，标记任务和阶段为失败
            task.status = "failed"
            task.progress = 100
            task.error_message = str(exc)
            task.finished_at = datetime.utcnow()
            project_workflow_state.mark_project_stage_failed(project, "image", task.id)
            await db.commit()
            raise

    async def _get_project(self, db: AsyncSession, project_id: int) -> Project:
        """查询项目，不存在时抛出异常。"""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        return project

    async def _get_frames(self, db: AsyncSession, project_id: int) -> list[Frame]:
        """查询项目的所有分镜，按序号排序。"""
        result = await db.execute(select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence))
        return list(result.scalars().all())

    def _extract_reference_images(self, project: Project) -> list[str]:
        """向后兼容的参考图片提取包装方法。"""
        return extract_reference_images(project)

    def _extract_product_images(self, project: Project) -> dict | None:
        """从项目的商品信息中提取主图列表，用于图片生成时的参考。"""
        if not project.product_info:
            return None
        try:
            product_data = json.loads(project.product_info)
        except (json.JSONDecodeError, TypeError):
            return None
        main_images = product_data.get("main_images", [])
        return {"商品主图": main_images} if main_images else None


image_workflow_service = ImageWorkflowService()
