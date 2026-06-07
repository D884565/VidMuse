"""对话式工作流调度服务：根据用户消息分发到不同的工作流动作。"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# TODO: RAG 依赖已移除，后续单独集成
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.stages.image_workflow import image_workflow_service
from backend.v1.app.script.service.script_generation_service import script_generation_service
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.generate.service.stages.video_workflow import video_generation_service
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.chat.intent_service import intent_service
from backend.v1.app.generate.service.workflow.blocks import (
    build_progress_block,
    build_script_stage_blocks,
    build_frame_editor_block,
    build_confirmation_preview_block,
)
from backend.v1.app.models.conversation import Conversation
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project

logger = logging.getLogger(__name__)

EDITABLE_FRAME_FIELDS = ("description", "narration", "image_prompt", "video_prompt")
PROJECT_REGENERATION_ACTIONS = {
    "REGENERATE_PROJECT_ALL",
    "REGENERATE_IMAGES_AND_VIDEO",
    "REGENERATE_VIDEO_ONLY",
}


def apply_frame_modifications(frame, modifications: dict) -> None:
    """Apply chat-driven frame edits while keeping generation prompts consistent."""
    if not modifications:
        return

    explicit_image_prompt = "image_prompt" in modifications
    for field, value in modifications.items():
        if hasattr(frame, field) and field in EDITABLE_FRAME_FIELDS:
            setattr(frame, field, value)
        elif field == "duration" and value is not None:
            try:
                frame.duration = max(1.0, float(value))
            except (TypeError, ValueError):
                pass

    if "description" in modifications and not explicit_image_prompt:
        frame.image_prompt = modifications["description"]

    # 旁白溢出检测：预估 TTS 时长，溢出则写入 ai_params 警告
    if "narration" in modifications and modifications["narration"]:
        estimated = len(modifications["narration"]) / 3
        dur = float(frame.duration or 5)
        if estimated > dur * 1.5:
            ai_params = dict(frame.ai_params or {})
            ai_params["tts_overflow_warning"] = {
                "narration_chars": len(modifications["narration"]),
                "estimated_seconds": round(estimated),
                "duration": dur,
            }
            frame.ai_params = ai_params


class ChatService:
    """对话式项目调度服务。

    使用 intent_service（LLM驱动）进行统一意图识别，
    根据识别结果分发到不同的工作流动作。
    只有用户明确确认图片进入视频阶段时，才触发昂贵的视频生成。
    """

    def __init__(self, rag_service=None):
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
        metadata: dict | None = None,
    ) -> dict:
        project = await self._get_project(db, project_id)
        db.add(Conversation(
            project_id=project_id,
            role="user",
            content=content,
            frame_id=frame_id,
            message_type="text",
            stage=project.workflow_stage,
            metadata_=metadata or None,
        ))
        await db.commit()

        frames = await self._get_frames(db, project_id)

        # 获取最近对话历史作为 LLM context
        history = await self._get_recent_conversations(db, project_id)

        # 统一意图识别（LLM驱动，失败时内部降级到极简规则）
        plan = intent_service.classify_project(
            content=content,
            workflow_stage=project.workflow_stage,
            stage_status=project.stage_status,
            frames=frames,
            conversation_history=history,
        )

        task_result = None
        updated_frames = []
        blocks = []
        pending_action = None

        if plan["action"] == "GENERATE_SCRIPT":
            task_result, blocks = await self._generate_script_from_chat(db, project, project_id, metadata=metadata)
            plan["assistant_content"] = (
                "风格和分镜方案已经就位，下面是剧本与画面方案。"
                "你先看一下节奏、卖点和每个镜头的画面方向；如果没问题，回复「继续」或「可以生成图片」，我就开始生成首帧图片。"
                "如果哪里不满意，直接告诉我要改哪一段。"
            )
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
        elif plan["action"] in PROJECT_REGENERATION_ACTIONS:
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    plan["action"],
                    plan["assistant_content"],
                    target_frames=plan.get("affected_frame_ids", []),
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                task_result = await self._submit_project_regeneration(db, project, project_id, plan["action"])
                blocks = [build_progress_block(
                    plan.get("affected_stage") or "video",
                    "running",
                    task_result.get("task_id"),
                    "Project regeneration has been queued from chat.",
                )]
        elif plan["action"] == "CHANGE_BGM":
            updated_frames, blocks = await self._handle_change_bgm(db, project, project_id)
        elif plan["action"] == "CONVERSE":
            # 普通对话，不触发任何工作流操作
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

    async def handle_message_stream(
        self,
        db: AsyncSession,
        project_id: int,
        content: str,
        frame_id: int | None = None,
        metadata: dict | None = None,
    ):
        """流式版本的 handle_message，通过 SSE 逐事件返回结果。"""

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 1. 保存用户消息
        project = await self._get_project(db, project_id)
        user_message = Conversation(
            project_id=project_id, role="user", content=content,
            frame_id=frame_id, message_type="text", stage=project.workflow_stage,
            metadata_=metadata or None,
        )
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)

        frames = await self._get_frames(db, project_id)
        history = await self._get_recent_conversations(db, project_id)

        # 2. 立刻告知前端"正在思考"，避免 LLM plan() 阻塞期间前端无反馈
        yield sse("thinking", {"message": "正在理解你的意图..."})
        await asyncio.sleep(0)

        # 3. 统一意图识别（LLM驱动，内部有极简降级）
        plan = intent_service.classify_project(
            content=content,
            workflow_stage=project.workflow_stage,
            stage_status=project.stage_status,
            frames=frames,
            conversation_history=history,
        )

        action = plan["action"]

        # 4. 发送 start 事件
        yield sse("start", {"action": action})

        # 5. 流式输出文本
        full_content = ""
        if action == "CONVERSE":
            local_text = plan.get("assistant_content", "")
            if local_text:
                full_content = local_text
                for char in local_text:
                    yield sse("token", {"content": char})
                    await asyncio.sleep(0.02)
            else:
                # 使用intent_service的流式对话
                for chunk in intent_service.stream_converse(
                    content=content,
                    workflow_stage=project.workflow_stage,
                    stage_status=project.stage_status,
                    frame_count=len(frames),
                    conversation_history=history,
                ):
                    full_content += chunk
                    yield sse("token", {"content": chunk})
        else:
            text = plan.get("assistant_content", "")
            full_content = text
            for char in text:
                yield sse("token", {"content": char})
                await asyncio.sleep(0.02)

        # 5. 执行动作
        task_result = None
        updated_frames = []
        blocks = []
        pending_action = None

        if action == "GENERATE_SCRIPT":
            task_result, blocks = await self._generate_script_from_chat(db, project, project_id, metadata=metadata)
        elif action == "CONFIRM_AND_ADVANCE":
            task_result, blocks = await self._handle_confirm_and_advance(db, project, project_id)
        elif action == "GENERATE_IMAGES":
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "图片生成已排队。")]
        elif action == "GENERATE_VIDEO":
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "视频生成已排队。")]
        elif action == "EDIT_FRAME":
            updated_frames, blocks = await self._handle_edit_frame(db, project, plan["affected_frame_ids"], plan.get("modifications", {}))
        elif action == "REGENERATE_FRAME_IMAGE":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block("REGENERATE_FRAME_IMAGE", plan["assistant_content"],
                    target_frames=plan["affected_frame_ids"], modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"])]
            else:
                updated_frames, task_result = await self._submit_frame_image_regeneration_tasks(db, project, plan["affected_frame_ids"], content)
                blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已提交图片重生成。")]
        elif action == "REGENERATE_FRAME_VIDEO":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block("REGENERATE_FRAME_VIDEO", plan["assistant_content"],
                    target_frames=plan["affected_frame_ids"], modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"])]
            else:
                updated_frames, task_result = await self._submit_frame_video_regeneration_tasks(db, project, plan["affected_frame_ids"])
                blocks = [build_progress_block("video", "running", task_result.get("task_id"), "已提交视频重生成。")]
        elif action == "REGENERATE_TTS":
            task_result = await self._submit_project_tts_regeneration_task(db, project, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "TTS 重生成已排队。")]
        elif action in PROJECT_REGENERATION_ACTIONS:
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(action, plan["assistant_content"],
                    target_frames=plan.get("affected_frame_ids", []), modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"])]
            else:
                task_result = await self._submit_project_regeneration(db, project, project_id, action)
                blocks = [build_progress_block(plan.get("affected_stage") or "video", "running", task_result.get("task_id"), "Project regeneration has been queued.")]
        elif action == "CHANGE_BGM":
            updated_frames, blocks = await self._handle_change_bgm(db, project, project_id)

        # 6. 发送 blocks 事件
        task_id = task_result.get("task_id") if task_result else project.last_task_id
        if blocks:
            yield sse("blocks", {"blocks": blocks, "stage": project.workflow_stage, "task_id": task_id})

        # 7. 保存 assistant 消息到 DB
        assistant_message = Conversation(
            project_id=project_id, role="assistant", content=full_content,
            message_type="stage_card" if blocks else "text",
            stage=plan.get("affected_stage", "") or project.workflow_stage,
            blocks=blocks, action_type=action, task_id=task_id,
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

        # 8. 发送 done 事件
        yield sse("done", {
            "action": action,
            "message_id": assistant_message.id,
            "stage": project.workflow_stage,
            "task_id": task_id,
            "updated_frames": updated_frames,
        })

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
        elif plan["action"] in PROJECT_REGENERATION_ACTIONS:
            task_result = await self._submit_project_regeneration(db, project, project_id, plan["action"])
            blocks = [build_progress_block(plan.get("affected_stage") or "video", "running", task_result.get("task_id"))]
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
        """处理 EDIT_FRAME 动作：修改分镜字段并返回 frame_editor blocks。
        如果修改了影响图片的字段且工作流已过 script 阶段，自动触发图片重生成。
        """
        if not frame_ids or not modifications:
            return [], []

        result = await db.execute(select(Frame).where(Frame.project_id == project.id, Frame.id.in_(frame_ids)))
        frames = list(result.scalars().all())
        updated = []
        blocks = []

        # 判断是否修改了影响图片的字段
        image_affecting_fields = {"description", "image_prompt"}
        affects_image = bool(image_affecting_fields & set(modifications.keys()))
        should_regen_image = affects_image and project.workflow_stage in ("image", "video", "completed")

        for frame in frames:
            apply_frame_modifications(frame, modifications)
            frame.dirty = 1
            updated.append({"frame_id": frame.id, "sequence": frame.sequence})
            blocks.append(build_frame_editor_block(frame))

        # 修改分镜后回退工作流状态
        # 如果需要重生成图片，由 _mark_frames_for_image_regeneration 统一处理失效
        if not should_regen_image:
            if project.workflow_stage == "completed":
                generation_workflow_service.invalidate_from(project, "video")
            elif project.workflow_stage in ("video", "image"):
                generation_workflow_service.invalidate_from(project, "image")
            else:
                generation_workflow_service.invalidate_from(project, "script")
            await db.commit()
        else:
            await db.flush()
            # 如果项目已完成，先失效视频阶段，再由图片重生成处理 image 阶段失效
            if project.workflow_stage == "completed":
                generation_workflow_service.invalidate_from(project, "video")
            # 自动触发图片重生成（内部会处理工作流失效和 commit）
            instruction = "剧本修改后自动重生成图片"
            _, task_result = await self._submit_frame_image_regeneration_tasks(
                db, project, frame_ids, instruction
            )
            blocks.append(build_progress_block(
                "image",
                "running",
                task_result.get("task_id"),
                "剧本已修改，对应图片正在重新生成。",
            ))

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

        # 查找上次使用的 BGM ID，排除它确保换到不同的
        exclude_ids = []
        bgm_id = bgm_selector_service.select_bgm(db, script_content, exclude_ids=exclude_ids)
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
        metadata: dict | None = None,
    ) -> tuple[dict, list[dict]]:
        task = await generation_task_service.create_task(db, project_id, "script", status="running")
        try:
            project_workflow_state.mark_project_stage_running(project, "script", task.id)
            await db.commit()
            local_refs = (metadata or {}).get("local_references") or []
            frames = await script_generation_service.generate_script(
                db, project_id,
                local_references=local_refs,
            )
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
            task_id = task.id
            await db.rollback()
            project = await self._get_project(db, project_id)
            task = await generation_task_service.get_task_model(db, task_id)
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

    async def submit_project_tts_regeneration_task(
        self,
        db: AsyncSession,
        project_id: int,
    ) -> dict:
        """Public entrypoint for detail-page project TTS regeneration."""
        project = await self._get_project(db, project_id)
        return await self._submit_project_tts_regeneration_task(db, project, project_id)

    async def _submit_project_regeneration(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
        action: str,
    ) -> dict:
        if project.stage_status == "running":
            return {
                "task_id": project.last_task_id,
                "status": "running",
                "message": "generation already in progress",
            }

        if action == "REGENERATE_PROJECT_ALL":
            await script_generation_service.generate_script(db, project_id, force=True)
            project = await self._get_project(db, project_id)
            frames = await self._get_frames(db, project_id)
            for frame in frames:
                frame.image_url = None
                frame.video_url = None
                frame.status = 0
                frame.dirty = 1
            project_workflow_state.mark_project_stage_review(project, "script", project.last_task_id)
            await db.commit()
            return await video_generation_service.submit_generation_task(
                db,
                project_id,
                require_ready_images=False,
                trigger_source="chat_regenerate_project_all",
            )

        frames = await self._get_frames(db, project_id)
        for frame in frames:
            if action == "REGENERATE_IMAGES_AND_VIDEO":
                frame.image_url = None
                frame.video_url = None
                frame.status = 0
            elif action == "REGENERATE_VIDEO_ONLY":
                frame.video_url = None
            else:
                raise ValueError(f"unsupported project regeneration action: {action}")
            frame.dirty = 1

        if action == "REGENERATE_IMAGES_AND_VIDEO":
            generation_workflow_service.invalidate_from(project, "image")
            project_workflow_state.mark_project_stage_review(project, "script", project.last_task_id)
            require_ready_images = False
            trigger_source = "chat_regenerate_images_and_video"
        else:
            generation_workflow_service.invalidate_from(project, "video")
            project_workflow_state.mark_project_stage_review(project, "image", project.last_task_id)
            require_ready_images = True
            trigger_source = "chat_regenerate_video_only"

        await db.commit()
        return await video_generation_service.submit_generation_task(
            db,
            project_id,
            require_ready_images=require_ready_images,
            trigger_source=trigger_source,
        )

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
