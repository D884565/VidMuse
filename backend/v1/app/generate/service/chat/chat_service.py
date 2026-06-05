"""对话式工作流调度服务：根据用户消息分发到不同的工作流动作。"""
from __future__ import annotations

import uuid
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
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.workflow.agent import workflow_agent_service
from backend.v1.app.generate.service.workflow.llm_agent import llm_agent_service
from backend.v1.app.generate.service.workflow.blocks import (
    build_progress_block,
    build_script_stage_blocks,
    build_frame_editor_block,
    build_confirmation_preview_block,
)
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

        # 获取最近对话历史作为 LLM context
        history = await self._get_recent_conversations(db, project_id)

        # 优先使用 LLM Agent，失败时降级到规则引擎
        plan = llm_agent_service.plan(
            project, frames, content, frame_id=frame_id, conversation_history=history
        )
        if plan is None:
            plan = workflow_agent_service.plan(project, frames, content, frame_id=frame_id)

        task_result = None
        updated_frames = []
        blocks = []
        pending_action = None

        if plan["action"] == "GENERATE_SCRIPT":
            task_result, blocks = await self._generate_script_from_chat(db, project, project_id)
            # 更新助手消息，提示用户确认并进入下一阶段
            plan["assistant_content"] = "剧本已生成完成！请查看下方分镜方案，如满意请说'确认并生成图片'，或告诉我需要修改的地方。"
        elif plan["action"] == "CONFIRM_AND_ADVANCE":
            task_result, blocks = await self._handle_confirm_and_advance(db, project, project_id)
        elif plan["action"] == "GENERATE_IMAGES":
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [
                build_progress_block(
                    "image",
                    "running",
                    task_result.get("task_id"),
                    "Image generation has been queued from chat.",
                )
            ]
        elif plan["action"] == "GENERATE_VIDEO":
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [
                build_progress_block(
                    "video",
                    "running",
                    task_result.get("task_id"),
                    "Video generation has been queued from chat.",
                )
            ]
        elif plan["action"] == "EDIT_FRAME":
            updated_frames, blocks = await self._handle_edit_frame(
                db, project, plan["affected_frame_ids"], plan.get("modifications", {})
            )
        elif plan["action"] == "REGENERATE_FRAME_IMAGE":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    "REGENERATE_FRAME_IMAGE",
                    plan["assistant_content"],
                    target_frames=plan["affected_frame_ids"],
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                updated_frames, task_result = await self._submit_frame_image_regeneration_tasks(
                    db, project, plan["affected_frame_ids"], content
                )
                blocks = [
                    build_progress_block(
                        "image",
                        "running",
                        task_result.get("task_id"),
                        "已记录图片修改要求，请使用图片阶段操作重生成对应图片。",
                    )
                ]
        elif plan["action"] == "REGENERATE_FRAME_VIDEO":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    "REGENERATE_FRAME_VIDEO",
                    plan["assistant_content"],
                    target_frames=plan["affected_frame_ids"],
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                updated_frames, task_result = await self._submit_frame_video_regeneration_tasks(
                    db, project, plan["affected_frame_ids"]
                )
                blocks = [
                    build_progress_block(
                        "video",
                        "running",
                        task_result.get("task_id"),
                        "已记录视频修改要求，将重新生成对应分镜视频。",
                    )
                ]
        elif plan["action"] == "REGENERATE_TTS":
            task_result = await self._submit_project_tts_regeneration_task(db, project, project_id)
            blocks = [
                build_progress_block(
                    "video",
                    "running",
                    task_result.get("task_id"),
                    "Project TTS regeneration has been queued from chat.",
                )
            ]
        elif plan["action"] == "CONFIRM_SCRIPT_AND_GENERATE_IMAGES":
            generation_workflow_service.advance_stage(project, "script")
            await db.commit()
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已确认剧本，正在生成分镜图片。")]
        elif plan["action"] == "REGENERATE_FRAME_IMAGE_LEGACY":
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
        elif plan["action"] == "CHANGE_BGM":
            updated_frames, blocks = await self._handle_change_bgm(db, project, project_id)
        elif plan["action"] == "CONVERSE":
            # 普通对话，不触发任何工作流操作
            blocks = []
        elif plan["action"] == "ASK_CLARIFYING_QUESTION":
            blocks = []
        elif plan["action"] == "ASK_CLARIFYING":
            blocks = []

        task_id = task_result.get("task_id") if task_result else project.last_task_id
        assistant_message = Conversation(
            project_id=project_id,
            role="assistant",
            content=plan["assistant_content"],
            message_type="stage_card" if blocks else "text",
            stage=plan.get("affected_stage", "") or project.workflow_stage,
            blocks=blocks,
            action_type=plan["action"],
            task_id=task_id,
            metadata_={
                "affected_frame_ids": plan.get("affected_frame_ids", []),
                "next_stage": plan.get("next_stage"),
                "estimated_cost_label": plan.get("estimated_cost_label", "low"),
                "needs_confirmation": plan.get("needs_confirmation", False),
                "pending_action": pending_action,
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
            "affected_frame_ids": plan.get("affected_frame_ids", []),
            "updated_frames": updated_frames,
            "workflow_stage": project.workflow_stage,
            "stage_status": project.stage_status,
            "task_id": task_id,
        }

    async def _handle_confirm_and_advance(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
    ) -> tuple[dict, list[dict]]:
        """处理 CONFIRM_AND_ADVANCE 动作：根据当前阶段确认并推进。"""
        stage = project.workflow_stage
        if stage == "script":
            generation_workflow_service.advance_stage(project, "script")
            await db.commit()
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已确认剧本，正在生成分镜图片。")]
            return task_result, blocks
        elif stage == "image":
            generation_workflow_service.advance_stage(project, "image")
            await db.commit()
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "已确认图片，正在生成视频。")]
            return task_result, blocks
        elif stage == "video":
            generation_workflow_service.advance_stage(project, "video")
            project_workflow_state.mark_project_completed(project, project.last_task_id)
            await db.commit()
            return {}, [build_progress_block("completed", "confirmed", project.last_task_id, "视频已确认完成。")]
        return {}, []

    def _build_pending_action(self, plan: dict, content: str, frame_id: int | None) -> dict:
        return {
            "id": uuid.uuid4().hex,
            "status": "pending",
            "action": plan["action"],
            "assistant_content": plan.get("assistant_content", ""),
            "affected_frame_ids": plan.get("affected_frame_ids", []),
            "modifications": plan.get("modifications", {}),
            "affected_stage": plan.get("affected_stage"),
            "next_stage": plan.get("next_stage"),
            "estimated_cost_label": plan.get("estimated_cost_label", "low"),
            "content": content,
            "frame_id": frame_id,
        }

    async def confirm_pending_action(
        self,
        db: AsyncSession,
        project_id: int,
        pending_action_id: str,
    ) -> dict:
        pending_message = await self._get_pending_action_message(db, project_id, pending_action_id)
        pending_action = (pending_message.metadata_ or {}).get("pending_action") or {}
        if pending_action.get("status") != "pending":
            raise ValueError(f"pending action is not pending: {pending_action_id}")

        project = await self._get_project(db, project_id)
        plan = {
            "action": pending_action["action"],
            "assistant_content": pending_action.get("assistant_content") or "Pending action confirmed.",
            "affected_frame_ids": pending_action.get("affected_frame_ids", []),
            "modifications": pending_action.get("modifications", {}),
            "affected_stage": pending_action.get("affected_stage"),
            "next_stage": pending_action.get("next_stage"),
            "estimated_cost_label": pending_action.get("estimated_cost_label", "low"),
            "needs_confirmation": False,
        }
        task_result, updated_frames, blocks = await self._execute_confirmed_plan(
            db,
            project,
            project_id,
            plan,
            pending_action.get("content", ""),
        )
        pending_action["status"] = "confirmed"
        pending_message.metadata_ = {**(pending_message.metadata_ or {}), "pending_action": pending_action}

        task_id = task_result.get("task_id") if task_result else project.last_task_id
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content=plan["assistant_content"],
            message_type="stage_card" if blocks else "text",
            stage=plan.get("affected_stage", "") or project.workflow_stage,
            blocks=blocks,
            action_type=plan["action"],
            task_id=task_id,
            metadata_={
                "affected_frame_ids": plan.get("affected_frame_ids", []),
                "pending_action_id": pending_action_id,
                "pending_action_status": "confirmed",
            },
        ))
        await db.commit()
        return {
            "pending_action_id": pending_action_id,
            "status": "confirmed",
            "action": plan["action"],
            "task_id": task_id,
            "updated_frames": updated_frames,
            "blocks": blocks,
        }

    async def cancel_pending_action(
        self,
        db: AsyncSession,
        project_id: int,
        pending_action_id: str,
    ) -> dict:
        pending_message = await self._get_pending_action_message(db, project_id, pending_action_id)
        pending_action = (pending_message.metadata_ or {}).get("pending_action") or {}
        pending_action["status"] = "cancelled"
        pending_message.metadata_ = {**(pending_message.metadata_ or {}), "pending_action": pending_action}
        await db.commit()
        return {"pending_action_id": pending_action_id, "status": "cancelled"}

    async def _execute_confirmed_plan(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
        plan: dict,
        content: str,
    ) -> tuple[dict | None, list[dict], list[dict]]:
        task_result = None
        updated_frames = []
        blocks = []
        if plan["action"] == "REGENERATE_FRAME_IMAGE":
            updated_frames, task_result = await self._submit_frame_image_regeneration_tasks(
                db, project, plan.get("affected_frame_ids", []), content
            )
            blocks = [build_progress_block("image", "running", task_result.get("task_id"))]
        elif plan["action"] == "REGENERATE_FRAME_VIDEO":
            updated_frames, task_result = await self._submit_frame_video_regeneration_tasks(
                db, project, plan.get("affected_frame_ids", [])
            )
            blocks = [build_progress_block("video", "running", task_result.get("task_id"))]
        elif plan["action"] == "REGENERATE_TTS":
            task_result = await self._submit_project_tts_regeneration_task(db, project, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"))]
        elif plan["action"] == "GENERATE_IMAGES":
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"))]
        elif plan["action"] == "GENERATE_VIDEO":
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"))]
        else:
            raise ValueError(f"unsupported pending action: {plan['action']}")
        return task_result, updated_frames, blocks

    async def _get_pending_action_message(
        self,
        db: AsyncSession,
        project_id: int,
        pending_action_id: str,
    ) -> Conversation:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.id.desc())
        )
        for conversation in result.scalars().all():
            pending_action = (conversation.metadata_ or {}).get("pending_action") or {}
            if pending_action.get("id") == pending_action_id:
                return conversation
        raise ValueError(f"pending action not found: {pending_action_id}")

    async def _handle_edit_frame(
        self,
        db: AsyncSession,
        project: Project,
        frame_ids: list[int],
        modifications: dict,
    ) -> tuple[list[dict], list[dict]]:
        """处理 EDIT_FRAME 动作：修改分镜字段并返回 frame_editor blocks。"""
        if not frame_ids or not modifications:
            return [], []

        result = await db.execute(select(Frame).where(Frame.project_id == project.id, Frame.id.in_(frame_ids)))
        frames = list(result.scalars().all())
        updated = []
        blocks = []

        for frame in frames:
            for field, value in modifications.items():
                if hasattr(frame, field) and field in ("description", "narration", "image_prompt", "video_prompt"):
                    setattr(frame, field, value)
                elif field == "duration" and value is not None:
                    try:
                        frame.duration = float(value)
                    except (TypeError, ValueError):
                        pass
            frame.dirty = 1
            updated.append({"frame_id": frame.id, "sequence": frame.sequence})
            blocks.append(build_frame_editor_block(frame))

        # 修改分镜后回退工作流状态
        if project.workflow_stage == "completed":
            generation_workflow_service.invalidate_from(project, "video")
        elif project.workflow_stage in ("video", "image"):
            generation_workflow_service.invalidate_from(project, "image")
        else:
            generation_workflow_service.invalidate_from(project, "script")

        await db.commit()
        return updated, blocks

    async def _handle_change_bgm(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
    ) -> tuple[list[dict], list[dict]]:
        """处理 CHANGE_BGM 动作：重新选择 BGM 并触发视频重生成。"""
        from backend.v1.app.generate.service.stages.bgm_selector import bgm_selector_service
        from backend.v1.app.models.script import Script

        # 获取当前剧本内容
        script_result = await db.execute(
            select(Script).where(Script.project_id == project_id).order_by(Script.version.desc()).limit(1)
        )
        script = script_result.scalar_one_or_none()
        script_content = script.content if script and script.content else {}

        # 选择新 BGM（不排除已使用的，让用户可以反复换）
        bgm_id = bgm_selector_service.select_bgm(db, script_content)
        if not bgm_id:
            return [], [{
                "type": "text",
                "content": "BGM 库为空，请先导入背景音乐文件。",
            }]

        # 触发视频重生成（如果项目已完成或在视频阶段）
        if project.workflow_stage in ("video", "completed"):
            generation_workflow_service.invalidate_from(project, "video")
            await db.commit()
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            return [], [build_progress_block(
                "video", "running", task_result.get("task_id"),
                f"已更换背景音乐（BGM #{bgm_id}），正在重新生成视频。",
            )]

        return [], [{
            "type": "text",
            "content": f"已选择新的背景音乐（BGM #{bgm_id}），将在视频生成时使用。",
        }]

    async def _get_recent_conversations(
        self,
        db: AsyncSession,
        project_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """获取最近的对话历史，用于 LLM context。"""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.id.desc())
            .limit(limit)
        )
        conversations = list(result.scalars().all())
        conversations.reverse()  # 按时间正序
        return [
            {"role": c.role, "content": c.content or ""}
            for c in conversations
            if c.content
        ]

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

    async def _submit_frame_image_regeneration_tasks(
        self,
        db: AsyncSession,
        project: Project,
        frame_ids: list[int],
        instruction: str,
    ) -> tuple[list[dict], dict]:
        updated = await self._mark_frames_for_image_regeneration(db, project, frame_ids, instruction)
        task_ids = []
        for item in updated:
            frame_id = item["frame_id"]
            task = await generation_task_service.create_task(db, project.id, "frame_image", status="queued")
            sent = celery_app.send_task("generate_frame_image_task", args=[project.id, frame_id, task.id])
            await generation_task_service.set_celery_task_id(db, task.id, sent.id)
            task_ids.append(task.id)
        return updated, {"task_id": task_ids[0] if task_ids else None, "task_ids": task_ids, "status": "queued"}

    async def _submit_frame_video_regeneration_tasks(
        self,
        db: AsyncSession,
        project: Project,
        frame_ids: list[int],
    ) -> tuple[list[dict], dict]:
        if not frame_ids:
            return [], {"task_id": None, "task_ids": [], "status": "skipped"}

        result = await db.execute(select(Frame).where(Frame.project_id == project.id, Frame.id.in_(frame_ids)))
        frames = list(result.scalars().all())
        updated = []
        for frame in frames:
            frame.dirty = 1
            updated.append({"frame_id": frame.id, "sequence": frame.sequence})
        generation_workflow_service.invalidate_from(project, "video")
        await db.commit()

        task_ids = []
        for item in updated:
            frame_id = item["frame_id"]
            task = await generation_task_service.create_task(db, project.id, "frame_video", status="queued")
            sent = celery_app.send_task("generate_frame_video_task", args=[project.id, frame_id, task.id])
            await generation_task_service.set_celery_task_id(db, task.id, sent.id)
            task_ids.append(task.id)
        return updated, {"task_id": task_ids[0] if task_ids else None, "task_ids": task_ids, "status": "queued"}

    async def _submit_project_tts_regeneration_task(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
    ) -> dict:
        task = await generation_task_service.create_task(db, project_id, "tts", status="queued")
        generation_workflow_service.invalidate_from(project, "video")
        await db.commit()
        sent = celery_app.send_task("generate_project_tts_task", args=[project_id, task.id])
        await generation_task_service.set_celery_task_id(db, task.id, sent.id)
        return {"task_id": task.id, "status": "queued"}

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
