"""对话式工作流调度服务：根据用户消息分发到不同的工作流动作。"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
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
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.project_asset import ProjectAsset

logger = logging.getLogger(__name__)

EDITABLE_FRAME_FIELDS = ("description", "narration", "image_prompt", "video_prompt", "subtitle_text", "text_overlay")
PROJECT_REGENERATION_ACTIONS = {
    "REGENERATE_PROJECT_ALL",
    "REGENERATE_IMAGES_AND_VIDEO",
    "REGENERATE_VIDEO_ONLY",
}
PRICE_TEXT_FIELDS = ("description", "narration", "image_prompt", "subtitle_text", "text_overlay")


def _extract_numeric_price_tokens(price_text: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for char in str(price_text or ""):
        if char.isdigit() or char == ".":
            current += char
            continue
        if current:
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    return tokens


def _apply_price_modification(frame, new_price: str) -> None:
    ai_params = dict(getattr(frame, "ai_params", None) or {})
    original_candidates: list[str] = []
    for field in PRICE_TEXT_FIELDS:
        current = getattr(frame, field, None)
        if isinstance(current, str):
            original_candidates.extend(_extract_numeric_price_tokens(current))
    for field in PRICE_TEXT_FIELDS:
        current = getattr(frame, field, None)
        if not isinstance(current, str) or "元" not in current:
            continue

        rebuilt = []
        token = ""
        replaced = False
        for char in current:
            if char.isdigit() or char in ".¥￥":
                token += char
                continue
            if char == "元" and any(ch.isdigit() for ch in token):
                rebuilt.append(new_price)
                token = ""
                replaced = True
                continue
            if token:
                rebuilt.append(token)
                token = ""
            rebuilt.append(char)
        if token:
            rebuilt.append(token)
        if replaced:
            setattr(frame, field, "".join(rebuilt))
    ai_params["price_revision_target"] = new_price
    if original_candidates:
        deduped = []
        for token in original_candidates:
            if token not in deduped:
                deduped.append(token)
        ai_params["price_revision_original"] = deduped[0] if len(deduped) == 1 else deduped
    frame.ai_params = ai_params


def _apply_single_modification(frame, field: str, value) -> str | None:
    """对单个字段执行修改，返回实际修改后的值（用于级联同步）。支持 replace 指令和整段覆写。"""
    if not hasattr(frame, field) or field not in EDITABLE_FRAME_FIELDS:
        return None

    current = getattr(frame, field) or ""

    # 替换指令格式：{"replace": ["旧文本", "新文本"]}
    if isinstance(value, dict) and "replace" in value:
        old, new = value["replace"]
        if old in current:
            new_value = current.replace(old, new)
            setattr(frame, field, new_value)
            return new_value
        return current

    # 整段覆写格式：直接赋值
    if isinstance(value, str):
        setattr(frame, field, value)
        return value

    return current


def apply_frame_modifications(frame, modifications: dict) -> None:
    """Apply chat-driven frame edits while keeping generation prompts consistent.

    支持两种 modifications 格式：
    - 替换指令: {"field": {"replace": ["old", "new"]}} — 精确文本替换
    - 整段覆写: {"field": "new_value"} — 直接赋值（兼容旧格式）
    """
    if not modifications:
        return

    # 处理价格特殊逻辑（兼容旧格式）
    price_value = modifications.get("price")
    if isinstance(price_value, str) and price_value.strip():
        _apply_price_modification(frame, price_value.strip())

    explicit_image_prompt = "image_prompt" in modifications
    description_new_value = None

    for field, value in modifications.items():
        if field == "price":
            continue  # 已在上面处理
        if field == "duration" and value is not None:
            try:
                dur_val = value.get("replace", [None, None])[1] if isinstance(value, dict) else value
                frame.duration = max(1.0, float(dur_val))
            except (TypeError, ValueError):
                pass
            continue

        result = _apply_single_modification(frame, field, value)
        if field == "description":
            description_new_value = result

    # description 变化时自动同步 image_prompt（除非 image_prompt 被显式修改）
    # 如果 description 用 replace 格式，对 image_prompt 也做同样的 replace 而非整段覆盖
    if description_new_value is not None and not explicit_image_prompt:
        desc_mod = modifications.get("description")
        if isinstance(desc_mod, dict) and "replace" in desc_mod:
            old, new = desc_mod["replace"]
            current_img = getattr(frame, "image_prompt") or ""
            if old in current_img:
                frame.image_prompt = current_img.replace(old, new)
            # 如果 image_prompt 不包含旧文本，不覆盖
        else:
            frame.image_prompt = description_new_value

    # 旁白溢出检测：预估 TTS 时长，溢出则写入 ai_params 警告
    narration_value = modifications.get("narration")
    narration_text = None
    if isinstance(narration_value, dict) and "replace" in narration_value:
        narration_text = getattr(frame, "narration", None)
    elif isinstance(narration_value, str):
        narration_text = narration_value

    if narration_text:
        estimated = len(narration_text) / 3
        dur = float(frame.duration or 5)
        if estimated > dur * 1.5:
            ai_params = dict(frame.ai_params or {})
            ai_params["tts_overflow_warning"] = {
                "narration_chars": len(narration_text),
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

        task_id = task_result.get("task_id") if task_result else project.last_task_id
        if assistant_message is None:
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
                "client_id": (metadata or {}).get("assistant_client_id"),
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

        # 检测帧是否被编辑窗口改过（last_edited_at 比最近一条对话消息更新）
        recently_edited = self._detect_external_edits(frames, history)
        if recently_edited:
            edited_info = "、".join(f"第{e['sequence']}个(id={e['frame_id']})" for e in recently_edited)
            content = f"[系统提示：以下分镜在编辑窗口被修改过：{edited_info}，请基于最新状态操作]\n{content}"

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
        task_result = None
        updated_frames = []
        blocks = []
        pending_action = None
        assistant_message = None

        if action not in ("CONVERSE", "ASK_CLARIFYING"):
            full_content = plan.get("assistant_content", "")
            task_result, updated_frames, blocks, pending_action = await self._execute_action(
                db,
                project,
                project_id,
                plan,
                content,
                frame_id=frame_id,
                metadata=metadata,
            )

            task_id = task_result.get("task_id") if task_result else project.last_task_id
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
                    "client_id": (metadata or {}).get("assistant_client_id"),
                },
            )
            db.add(assistant_message)
            await db.commit()
            await db.refresh(assistant_message)

            for char in full_content:
                yield sse("token", {"content": char})
                await asyncio.sleep(0.02)
        elif action == "CONVERSE":
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
        # 5. 执行动作
        # 6. 发送 blocks 事件
        task_id = task_result.get("task_id") if task_result else project.last_task_id
        if blocks:
            yield sse("blocks", {"blocks": blocks, "stage": project.workflow_stage, "task_id": task_id})

        # 7. 保存 assistant 消息到 DB
        if assistant_message is None:
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
                    "client_id": (metadata or {}).get("assistant_client_id"),
                },
            )
            db.add(assistant_message)
            await db.commit()
            await db.refresh(assistant_message)

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
            project_workflow_state.mark_project_stage_running(project, "image", task_result.get("task_id"))
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已确认剧本，正在生成分镜图片。")]
            return task_result, blocks
        elif stage == "image":
            generation_workflow_service.advance_stage(project, "image")
            await db.commit()
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            project_workflow_state.mark_project_stage_running(project, "video", task_result.get("task_id"))
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "已确认图片，正在生成视频。")]
            return task_result, blocks
        elif stage == "video":
            generation_workflow_service.advance_stage(project, "video")
            project_workflow_state.mark_project_completed(project, project.last_task_id)
            await db.commit()
            return {}, [build_progress_block("completed", "confirmed", project.last_task_id, "视频已确认完成。")]
        return {}, []

    async def _execute_action(
        self,
        db: AsyncSession,
        project: Project,
        project_id: int,
        plan: dict,
        content: str,
        frame_id: int | None = None,
        metadata: dict | None = None,
    ) -> tuple[dict | None, list[dict], list[dict], dict | None]:
        task_result = None
        updated_frames = []
        blocks = []
        pending_action = None
        action = plan["action"]

        if action == "GENERATE_SCRIPT":
            task_result, blocks = await self._generate_script_from_chat(db, project, project_id, metadata=metadata)
            plan["assistant_content"] = (
                "风格和分镜方案已经就位，下面是剧本与画面方案。"
                "你先看一下节奏、卖点和每个镜头的画面方向；如果没问题，回复「继续」或「可以生成图片」，我就开始生成首帧图片。"
                "如果哪里不满意，直接告诉我要改哪一段。"
            )
        elif action == "CONFIRM_AND_ADVANCE":
            task_result, blocks = await self._handle_confirm_and_advance(db, project, project_id)
        elif action == "GENERATE_IMAGES":
            task_result = await image_workflow_service.submit_image_task(db, project_id)
            blocks = [build_progress_block("image", "running", task_result.get("task_id"), "图片生成已排队。")]
        elif action == "GENERATE_VIDEO":
            task_result = await video_generation_service.submit_generation_task(db, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "视频生成已排队。")]
        elif action == "EDIT_FRAME":
            task_result, updated_frames, blocks = await self._handle_edit_frame(
                db, project, plan.get("affected_frame_ids", []), plan.get("modifications", {})
            )
        elif action == "REGENERATE_FRAME_IMAGE":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    "REGENERATE_FRAME_IMAGE",
                    plan["assistant_content"],
                    target_frames=plan.get("affected_frame_ids", []),
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                updated_frames, task_result = await self._submit_frame_image_regeneration_tasks(
                    db, project, plan.get("affected_frame_ids", []), content
                )
                blocks = [build_progress_block("image", "running", task_result.get("task_id"), "已提交图片重生成。")]
        elif action == "REGENERATE_FRAME_VIDEO":
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    "REGENERATE_FRAME_VIDEO",
                    plan["assistant_content"],
                    target_frames=plan.get("affected_frame_ids", []),
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                updated_frames, task_result = await self._submit_frame_video_regeneration_tasks(
                    db, project, plan.get("affected_frame_ids", [])
                )
                blocks = [build_progress_block("video", "running", task_result.get("task_id"), "已提交视频重生成。")]
        elif action == "REGENERATE_TTS":
            task_result = await self._submit_project_tts_regeneration_task(db, project, project_id)
            blocks = [build_progress_block("video", "running", task_result.get("task_id"), "TTS 重生成已排队。")]
        elif action in PROJECT_REGENERATION_ACTIONS:
            if plan.get("needs_confirmation", True):
                pending_action = self._build_pending_action(plan, content, frame_id)
                blocks = [build_confirmation_preview_block(
                    action,
                    plan["assistant_content"],
                    target_frames=plan.get("affected_frame_ids", []),
                    modifications=plan.get("modifications", {}),
                    pending_action_id=pending_action["id"],
                )]
            else:
                task_result = await self._submit_project_regeneration(db, project, project_id, action)
                blocks = [build_progress_block(
                    plan.get("affected_stage") or "video",
                    "running",
                    task_result.get("task_id"),
                    "Project regeneration has been queued from chat.",
                )]
        elif action == "CHANGE_BGM":
            updated_frames, blocks = await self._handle_change_bgm(db, project, project_id)
        elif action == "CONVERSE":
            blocks = []
        elif action == "ASK_CLARIFYING":
            blocks = []

        return task_result, updated_frames, blocks, pending_action

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
        if plan["action"] not in {
            "REGENERATE_FRAME_IMAGE",
            "REGENERATE_FRAME_VIDEO",
            "REGENERATE_TTS",
            "GENERATE_IMAGES",
            "GENERATE_VIDEO",
            *PROJECT_REGENERATION_ACTIONS,
        }:
            raise ValueError(f"unsupported pending action: {plan['action']}")
        task_result, updated_frames, blocks, _ = await self._execute_action(
            db,
            project,
            project_id,
            {**plan, "needs_confirmation": False},
            content,
        )
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
    ) -> tuple[dict | None, list[dict], list[dict]]:
        """处理 EDIT_FRAME 动作：修改分镜字段并返回 frame_editor blocks。
        如果修改了影响图片的字段且工作流已过 script 阶段，自动触发图片重生成。
        """
        if not frame_ids or not modifications:
            return None, [], []

        result = await db.execute(select(Frame).where(Frame.project_id == project.id, Frame.id.in_(frame_ids)))
        frames = list(result.scalars().all())
        updated = []
        blocks = []
        task_result = None

        # 判断是否修改了影响图片的字段
        image_affecting_fields = {"description", "image_prompt", "price"}
        affects_image = bool(image_affecting_fields & set(modifications.keys()))
        should_regen_image = affects_image and project.workflow_stage in ("image", "video", "completed")

        # narration 修改标记 TTS dirty
        narration_affecting_fields = {"narration"}
        affects_narration = bool(narration_affecting_fields & set(modifications.keys()))
        should_regen_tts = affects_narration and project.workflow_stage in ("video", "completed") and not should_regen_image
        narration_only = affects_narration and set(modifications.keys()) <= narration_affecting_fields

        for frame in frames:
            apply_frame_modifications(frame, modifications)
            frame.dirty = 0 if narration_only else 1
            frame.version = (frame.version or 1) + 1
            frame.last_edited_at = datetime.utcnow()
            if should_regen_image:
                frame.image_url = None
                frame.video_url = None
                frame.status = 0
            # narration 修改且已过 script 阶段，标记 TTS dirty
            if affects_narration and project.workflow_stage in ("video", "completed"):
                ai_params = dict(frame.ai_params or {})
                ai_params["tts_dirty"] = True
                frame.ai_params = ai_params
            updated.append({"frame_id": frame.id, "sequence": frame.sequence})
            blocks.append(build_frame_editor_block(frame))

        # 修改分镜后回退工作流状态
        # 如果需要重生成图片，由 _mark_frames_for_image_regeneration 统一处理失效
        if should_regen_tts:
            await db.flush()
            generation_workflow_service.invalidate_from(project, "video")
            await db.commit()
            task_result = await video_generation_service.submit_generation_task(
                db,
                project.id,
                require_ready_images=True,
                trigger_source="chat_narration_edit",
            )
            blocks.append(build_progress_block(
                "video",
                "running",
                task_result.get("task_id"),
                "旁白已修改，正在重新合成带新配音的视频。",
            ))
        elif not should_regen_image:
            if project.workflow_stage == "script" and project.stage_status in ("awaiting_review", "confirmed"):
                project_workflow_state.mark_project_stage_review(project, "script", project.last_task_id)
            elif project.workflow_stage == "completed":
                generation_workflow_service.invalidate_from(project, "video")
            elif project.workflow_stage in ("video", "image"):
                generation_workflow_service.invalidate_from(project, "image")
            else:
                generation_workflow_service.invalidate_from(project, "script")
            await db.commit()
        else:
            updated, task_result = await self._submit_frame_image_regeneration_tasks(
                db,
                project,
                frame_ids,
                "镜头内容已修改，请重新生成这一张图片。",
            )
            blocks.append(build_progress_block(
                "image",
                "running",
                task_result.get("task_id"),
                "镜头内容已修改，正在重新生成这张图片。",
            ))

        return task_result, updated, blocks

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
        music_config = dict(getattr(project, "music_config", None) or {})
        current_bgm_id = music_config.get("current_bgm_id")
        exclude_ids = [int(current_bgm_id)] if current_bgm_id else []
        bgm_id = await bgm_selector_service.select_bgm_async(db, script_content, exclude_ids=exclude_ids)
        if not bgm_id:
            return [], [{
                "type": "text",
                "content": "BGM 库为空，请先导入背景音乐文件。",
            }]

        music_config["current_bgm_id"] = int(bgm_id)
        project.music_config = music_config

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
            {
                "role": c.role,
                "content": c.content or "",
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
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
            await self._bind_selected_assets_to_project(db, project_id, (metadata or {}).get("selected_assets") or [])
            local_refs = (metadata or {}).get("local_references") or []
            frames = await script_generation_service.generate_script(
                db, project_id,
                local_references=local_refs,
                force=True,
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

    async def _bind_selected_assets_to_project(
        self,
        db: AsyncSession,
        project_id: int,
        selected_assets: list[dict] | None,
    ) -> list[int]:
        asset_ids = []
        for item in selected_assets or []:
            try:
                asset_ids.append(int(item.get("id")))
            except (TypeError, ValueError, AttributeError):
                continue
        if not asset_ids:
            return []

        result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        assets = list(result.scalars().all())
        asset_map = {int(asset.id): asset for asset in assets if getattr(asset, "id", None) is not None}
        valid_ids = [asset_id for asset_id in asset_ids if asset_id in asset_map]
        if not valid_ids:
            return []

        existing_result = await db.execute(
            select(ProjectAsset.asset_id).where(
                ProjectAsset.project_id == project_id,
                ProjectAsset.asset_id.in_(valid_ids),
                ProjectAsset.role == "reference",
            )
        )
        existing_ids = set(existing_result.scalars().all())
        for asset_id in valid_ids:
            if asset_id not in existing_ids:
                db.add(ProjectAsset(project_id=project_id, asset_id=asset_id, role="reference"))
        await db.flush()
        return valid_ids

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

    @staticmethod
    def _detect_external_edits(frames: list[Frame], history: list[Conversation]) -> list[dict]:
        """检测帧是否被编辑窗口改过。

        比较帧的 last_edited_at 和最近一条对话消息的 created_at，
        如果帧更新，说明是编辑窗口的外部修改。
        """
        if not frames or not history:
            return []

        # 找最近一条对话消息的时间
        last_msg_time = None
        for msg in reversed(history):
            created_at = msg.get("created_at") if isinstance(msg, dict) else getattr(msg, "created_at", None)
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except ValueError:
                    created_at = None
            if created_at:
                last_msg_time = created_at
                break
        if not last_msg_time:
            return []

        edited = []
        for f in frames:
            if f.last_edited_at and f.last_edited_at > last_msg_time:
                edited.append({
                    "frame_id": f.id,
                    "sequence": f.sequence,
                    "edited_at": f.last_edited_at.isoformat(),
                })
        return edited


chat_service = ChatService()
