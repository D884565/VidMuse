"""对话式工作流调度服务：根据用户消息分发到不同的工作流动作。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.providers import VolcanoLLM
# TODO: RAG 依赖已移除，后续单独集成
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.stages.image_workflow import image_workflow_service
from backend.v1.app.generate.service.stages.script import script_generation_service
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.generate.service.stages.video_workflow import video_generation_service
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.workflow.agent import workflow_agent_service
from backend.v1.app.generate.service.workflow.blocks import build_progress_block, build_script_stage_blocks
from backend.v1.app.models.conversation import Conversation
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project


class ChatService:
    """对话式项目调度服务。

    这里不再把每条反馈都直接升级为整片重渲染，而是先让规则 Agent 判断动作。
    只有用户明确确认图片进入视频阶段时，才触发昂贵的视频生成。
    """

    def __init__(self, rag_service=None):
        self._llm = None
        self.rag_service = rag_service

    @property
    def llm(self):
        if self._llm is None:
            if VolcanoLLM is None:
                raise RuntimeError("VolcanoLLM 不可用，请安装 openai 依赖")
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    async def handle_message(
        self,
        db: AsyncSession,
        project_id: int,
        content: str,
        frame_id: int | None = None,
    ) -> dict:
        project = await self._get_project(db, project_id)
        db.add(Conversation(
            project_id=project_id,
            role="user",
            content=content,
            frame_id=frame_id,
            message_type="text",
            stage=project.workflow_stage,
        ))
        await db.commit()

        frames = await self._get_frames(db, project_id)
        plan = workflow_agent_service.plan(project, frames, content, frame_id=frame_id)
        task_result = None
        updated_frames = []
        blocks = []

        if plan["action"] == "GENERATE_SCRIPT":
            task_result, blocks = await self._generate_script_from_chat(db, project, project_id)
        elif plan["action"] == "CONFIRM_SCRIPT_AND_GENERATE_IMAGES":
            generation_workflow_service.advance_stage(project, "script")
            await db.commit()
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已确认剧本，正在生成分镜图片。")]
        elif plan["action"] == "REGENERATE_FRAME_IMAGE":
            updated_frames = await self._mark_frames_for_image_regeneration(
                db, project, plan["affected_frame_ids"], content
            )
            blocks = [
                build_progress_block(
                    "image",
                    "awaiting_review",
                    project.last_task_id,
                    "已记录图片修改要求，请使用图片阶段操作重生成对应图片。",
                )
            ]
        elif plan["action"] == "UPDATE_SCRIPT_TEXT":
            generation_workflow_service.invalidate_from(project, "script")
            blocks = [
                build_progress_block(
                    "script",
                    "awaiting_review",
                    project.last_task_id,
                    "已记录剧本修改要求，图片和视频需要重新确认。",
                )
            ]
            await db.commit()
        elif plan["action"] == "CONFIRM_IMAGES_AND_GENERATE_VIDEO":
            if project.workflow_stage == "image":
                generation_workflow_service.advance_stage(project, "image")
                await db.commit()
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "已确认图片，正在生成视频。")]
        elif plan["action"] == "CONFIRM_VIDEO":
            generation_workflow_service.advance_stage(project, "video")
            project_workflow_state.mark_project_completed(project, project.last_task_id)
            await db.commit()
            blocks = [build_progress_block("completed", "confirmed", project.last_task_id, "视频已确认完成。")]
        elif plan["action"] == "ASK_CLARIFYING_QUESTION":
            # 澄清类回复只写入对话，不创建任何高成本生成任务。
            blocks = []

        task_id = task_result.get("task_id") if task_result else project.last_task_id
        assistant_message = Conversation(
            project_id=project_id,
            role="assistant",
            content=plan["assistant_content"],
            message_type="stage_card" if blocks else "text",
            stage=plan["affected_stage"],
            blocks=blocks,
            action_type=plan["action"],
            task_id=task_id,
            metadata_={
                "affected_frame_ids": plan["affected_frame_ids"],
                "next_stage": plan["next_stage"],
                "estimated_cost_label": plan["estimated_cost_label"],
            },
        )
        db.add(assistant_message)
        await db.commit()

        return {
            "message": {
                "role": "assistant",
                "content": assistant_message.content,
                "blocks": blocks,
                "stage": assistant_message.stage,
                "action_type": assistant_message.action_type,
                "task_id": task_id,
            },
            "action": plan["action"],
            "affected_frame_ids": plan["affected_frame_ids"],
            "updated_frames": updated_frames,
            "workflow_stage": project.workflow_stage,
            "stage_status": project.stage_status,
            "task_id": task_id,
        }

    async def _generate_script_from_chat(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
    ) -> tuple[dict, list[dict]]:
        task = await generation_task_service.create_task(db, project_id, "script", status="running")
        try:
            project_workflow_state.mark_project_stage_running(project, "script", task.id)
            await db.commit()
            frames = await script_generation_service.generate_script(db, project_id)
            generation_workflow_service.mark_stage_review(project, "script", task.id)
            task.status = "succeeded"
            task.progress = 100
            task.current_step = "SCRIPT_GENERATED"
            from datetime import datetime
            task.finished_at = datetime.utcnow()
            await db.commit()
            return (
                {
                    "project_id": project_id,
                    "task_id": task.id,
                    "status": "script_ready",
                    "frames_count": len(frames),
                },
                build_script_stage_blocks(frames),
            )
        except Exception as exc:
            project_workflow_state.mark_project_stage_failed(project, "script", task.id)
            generation_workflow_service.fail_stage(project, "script", task.id)
            task.status = "failed"
            task.progress = 100
            task.error_message = str(exc)
            from datetime import datetime
            task.finished_at = datetime.utcnow()
            await db.commit()
            raise

    async def regenerate_frame(
        self,
        db: AsyncSession,
        project_id: int,
        frame_id: int,
        instruction: str | None = None,
    ) -> dict:
        frame = await self._get_frame(db, frame_id, project_id)
        if instruction:
            frame.description = f"{frame.description or ''}\n\n用户修改要求：{instruction}"
        frame.status = 0
        frame.dirty = 1
        project = await self._get_project(db, project_id)
        generation_workflow_service.invalidate_from(project, "script")
        await db.commit()
        return {
            "frame_id": frame.id,
            "sequence": frame.sequence,
            "description": frame.description,
            "status": "script_updated",
            "message": "分镜已标记为待重新生成，图片和视频需要重新确认。",
        }

    async def regenerate_frame_image(
        self,
        db: AsyncSession,
        project_id: int,
        frame_id: int,
        instruction: str | None = None,
    ) -> dict:
        frame = await self._get_frame(db, frame_id, project_id)
        await self._mark_frames_for_image_regeneration(
            db,
            await self._get_project(db, project_id),
            [frame.id],
            instruction or "重生成这张图片",
        )
        return {
            "frame_id": frame.id,
            "sequence": frame.sequence,
            "description": frame.description,
            "status": "image_pending_regenerate",
            "message": "图片已标记为待重生成，视频阶段已失效。",
        }

    async def _mark_frames_for_image_regeneration(
        self,
        db: AsyncSession,
        project: Project,
        frame_ids: list[int],
        instruction: str,
    ) -> list[dict]:
        if not frame_ids:
            return []
        result = await db.execute(select(Frame).where(Frame.project_id == project.id, Frame.id.in_(frame_ids)))
        frames = list(result.scalars().all())
        updated = []
        for frame in frames:
            # 只清空图片产物，不直接触发视频生成，避免用户一句反馈造成高成本调用。
            frame.image_url = None
            frame.status = 0
            frame.dirty = 1
            ai_params = dict(frame.ai_params or {})
            ai_params["image_revision_instruction"] = instruction
            frame.ai_params = ai_params
            updated.append({"frame_id": frame.id, "sequence": frame.sequence})
        generation_workflow_service.invalidate_from(project, "image")
        await db.commit()
        return updated

    async def _get_project(self, db: AsyncSession, project_id: int) -> Project:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        return project

    async def _get_frame(self, db: AsyncSession, frame_id: int, project_id: int) -> Frame:
        result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
        frame = result.scalar_one_or_none()
        if not frame:
            raise ValueError(f"分镜不存在: {frame_id}")
        return frame

    async def _get_frames(self, db: AsyncSession, project_id: int) -> list[Frame]:
        result = await db.execute(select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence))
        return list(result.scalars().all())


chat_service = ChatService()
