"""对话式调整服务"""
import asyncio
import json
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.conversation import Conversation
from backend.providers import VolcanoLLM, ChatRequest, ChatMessage
from backend.v1.app.generate.service._rag_temp.rag_service import (
    MockRAGService, RAGService, RAGResult,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_ROUNDS = 20


class ChatService:
    """对话式调整服务"""

    def __init__(self, rag_service: Optional[RAGService] = None):
        self.llm = VolcanoLLM(key=None, model_name=None)
        self.rag_service: RAGService = rag_service or MockRAGService()

    async def handle_message(
        self, db: AsyncSession, project_id: int, content: str, frame_id: int | None = None
    ) -> dict:
        """处理用户对话消息，返回调整结果"""
        project = await self._get_project(db, project_id)

        # 保存用户消息
        db.add(Conversation(
            project_id=project_id,
            role="user",
            content=content,
            frame_id=frame_id,
        ))
        await db.commit()

        # 读取对话历史
        history = await self._get_history(db, project_id)

        # 读取现有帧
        frames_result = await db.execute(
            select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence)
        )
        frames = list(frames_result.scalars())

        # LLM 判断影响范围 + 生成新内容
        if frame_id:
            affected_frames = [f for f in frames if f.id == frame_id]
            new_content = await self._regenerate_frames(
                db, project, affected_frames, history, content
            )
        else:
            new_content = await self._analyze_and_regenerate(
                db, project, frames, history, content
            )

        # 保存 assistant 响应
        summary = f"已根据您的要求调整了{len(new_content.get('updated_frames', []))}个场景"
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content=summary,
        ))
        await db.commit()

        return {
            "message": summary,
            "updated_frames": new_content.get("updated_frames", []),
        }

    async def regenerate_frame(
        self, db: AsyncSession, project_id: int, frame_id: int, instruction: str | None = None
    ) -> dict:
        """重新生成指定帧的脚本+图片"""
        project = await self._get_project(db, project_id)
        frame = await self._get_frame(db, frame_id, project_id)

        history = await self._get_history(db, project_id)
        prompt = self._build_frame_regenerate_prompt(project, frame, history, instruction)

        try:
            new_scene = await self._call_llm_for_scene(prompt)
            frame.description = new_scene.get("image_prompt", frame.description)
            frame.prompt = new_scene.get("video_prompt", frame.prompt)
            frame.text_overlay = new_scene.get("overlay_text", frame.text_overlay)
            frame.ai_params = {
                **(frame.ai_params or {}),
                "text": new_scene.get("text", ""),
                "camera": new_scene.get("camera", ""),
                "mood": new_scene.get("mood", ""),
            }
            frame.status = 0
            await db.commit()
            await db.refresh(frame)

            return {
                "frame_id": frame.id,
                "sequence": frame.sequence,
                "description": frame.description,
                "prompt": frame.prompt,
                "text_overlay": frame.text_overlay,
                "status": "script_updated",
                "message": "脚本已更新",
            }
        except Exception as e:
            logger.warning(f"[帧重新生成] LLM 调用失败: {e}")
            raise ValueError(f"重新生成失败: {e}")

    async def regenerate_frame_image(
        self, db: AsyncSession, project_id: int, frame_id: int, instruction: str | None = None
    ) -> dict:
        """只重新生成指定帧的图片（脚本不变）"""
        project = await self._get_project(db, project_id)
        frame = await self._get_frame(db, frame_id, project_id)

        image_prompt = frame.description or ""
        if instruction:
            image_prompt = f"{image_prompt}\n\n用户额外要求：{instruction}"

        frame.description = image_prompt
        frame.status = 0
        await db.commit()
        await db.refresh(frame)

        return {
            "frame_id": frame.id,
            "sequence": frame.sequence,
            "description": frame.description,
            "status": "image_pending_regenerate",
            "message": "图片将重新生成",
        }

    # ========== 内部方法 ==========

    async def _get_project(self, db: AsyncSession, project_id: int) -> Project:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        return project

    async def _get_frame(self, db: AsyncSession, frame_id: int, project_id: int) -> Frame:
        result = await db.execute(
            select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id)
        )
        frame = result.scalar_one_or_none()
        if not frame:
            raise ValueError(f"帧不存在: {frame_id}")
        return frame

    async def _get_history(self, db: AsyncSession, project_id: int) -> list[dict]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
            .limit(MAX_HISTORY_ROUNDS * 2)
        )
        messages = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content} for m in messages]

    async def _analyze_and_regenerate(
        self, db: AsyncSession, project: Project, frames: list[Frame], history: list[dict], user_message: str
    ) -> dict:
        frames_desc = "\n".join(
            f"  场景{f.sequence} (id={f.id}, type={f.scene_type}): {(f.description or '')[:80]}"
            for f in frames
        )

        analysis_prompt = (
            f"用户想要调整视频。以下是当前视频的场景列表：\n{frames_desc}\n\n"
            f"用户的调整要求：{user_message}\n\n"
            f"请判断影响范围，返回 JSON：{{\"scope\": \"all\" | \"single\", \"frame_id\": null | int}}"
        )

        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content="你是视频调整助手，判断用户想调整哪些场景。只返回JSON。"),
                ChatMessage(role="user", content=analysis_prompt),
            ],
            temperature=0.3,
            max_tokens=256,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.llm.chat, request)

        try:
            analysis = json.loads(response.content.strip().replace("```json", "").replace("```", ""))
        except json.JSONDecodeError:
            analysis = {"scope": "all", "frame_id": None}

        scope = analysis.get("scope", "all")

        if scope == "single":
            fid = analysis.get("frame_id")
            target = [f for f in frames if f.id == fid]
            if target:
                return await self._regenerate_frames(db, project, target, history, user_message)
            return {"updated_frames": []}

        return await self._regenerate_frames(db, project, frames, history, user_message)

    async def _regenerate_frames(
        self, db: AsyncSession, project: Project, frames: list[Frame], history: list[dict], instruction: str
    ) -> dict:
        updated = []
        for frame in frames:
            prompt = self._build_frame_regenerate_prompt(project, frame, history, instruction)
            try:
                new_scene = await self._call_llm_for_scene(prompt)
                frame.description = new_scene.get("image_prompt", frame.description)
                frame.prompt = new_scene.get("video_prompt", frame.prompt)
                frame.text_overlay = new_scene.get("overlay_text", frame.text_overlay)
                frame.ai_params = {
                    **(frame.ai_params or {}),
                    "text": new_scene.get("text", ""),
                    "camera": new_scene.get("camera", ""),
                    "mood": new_scene.get("mood", ""),
                }
                frame.status = 0
                updated.append({"frame_id": frame.id, "sequence": frame.sequence})
            except Exception as e:
                logger.warning(f"[对话调整] 帧 {frame.id} 重新生成失败: {e}")

        await db.commit()
        return {"updated_frames": updated}

    def _build_frame_regenerate_prompt(
        self, project: Project, frame: Frame, history: list[dict], instruction: str | None
    ) -> str:
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

        return (
            f"你是一个专业的带货视频编剧。请为以下场景重新生成内容。\n\n"
            f"## 商品信息\n- 标题：{project.title}\n- 描述：{project.description or '无'}\n\n"
            f"## 用户原始意图\n{project.user_prompt or '无'}\n\n"
            f"## 当前场景\n- 类型：{frame.scene_type}\n- 序号：{frame.sequence}\n"
            f"- 当前画面描述：{frame.description}\n\n"
            f"## 对话历史\n{history_text}\n\n"
            f"## 调整指令\n{instruction or '无额外指令'}\n\n"
            f"请返回 JSON：\n"
            f'{{"image_prompt": "新的画面描述", "video_prompt": "新的视频运动描述", '
            f'"text": "新的配音文案", "overlay_text": "叠加文字", '
            f'"camera": "镜头运动", "mood": "氛围"}}'
        )

    async def _call_llm_for_scene(self, prompt: str) -> dict:
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content="你是带货视频编剧。只返回JSON。"),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.llm.chat, request)

        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())


chat_service = ChatService()
