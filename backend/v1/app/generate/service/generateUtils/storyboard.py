"""分镜编辑服务 — 管理剧本版本和分镜帧的编辑操作。"""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.workflow.limits import validate_total_frame_duration, normalize_target_duration

# 允许前端通过 PATCH 接口修改的帧字段
EDITABLE_FRAME_FIELDS = {
    "narration",
    "subtitle_text",
    "subtitle_position",
    "image_prompt",
    "video_prompt",
    "duration",
    "sequence",
}


class StoryboardService:
    """提供剧本版本查询和分镜帧编辑能力。"""

    async def list_scripts(self, db: AsyncSession, project_id: int) -> list[dict[str, Any]]:
        """获取项目的所有剧本版本列表（按版本号倒序，不含 LLM 输出内容）。"""
        result = await db.execute(
            select(Script)
            .where(Script.project_id == project_id)
            .order_by(Script.version.desc())
        )
        return [self._script_to_dict(script, include_content=False) for script in result.scalars().all()]

    async def get_script(self, db: AsyncSession, project_id: int, script_id: int) -> dict[str, Any]:
        """获取单个剧本版本详情（含 prompt_snapshot、rag_snapshot、LLM 输出）。"""
        result = await db.execute(
            select(Script).where(Script.id == script_id, Script.project_id == project_id)
        )
        script = result.scalar_one_or_none()
        if not script:
            raise ValueError(f"script not found: {script_id}")
        return self._script_to_dict(script, include_content=True)

    async def update_frame(
        self,
        db: AsyncSession,
        project_id: int,
        frame_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """更新单个分镜帧的可编辑字段，标记为 dirty 并同步旧版字段。"""
        result = await db.execute(
            select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id)
        )
        frame = result.scalar_one_or_none()
        if not frame:
            raise ValueError(f"frame not found: {frame_id}")

        # 只更新白名单内的字段
        changed = False
        changed_fields: set[str] = set()
        for field, value in patch.items():
            if field not in EDITABLE_FRAME_FIELDS:
                continue
            if field == "duration":
                try:
                    value = max(1.0, float(value))
                except (TypeError, ValueError):
                    continue
            setattr(frame, field, value)
            changed = True
            changed_fields.add(field)

        if changed:
            project = await db.get(Project, project_id)
            duration_result = await db.execute(select(Frame).where(Frame.project_id == project_id))
            frames = list(duration_result.scalars().all())
            # 总时长校验，溢出则返回警告而不是抛异常
            durations = [float(item.duration or 0) for item in frames]
            total = sum(durations)
            limit = normalize_target_duration(project.target_duration if project else 15)
            if total > limit:
                await db.flush()
                return {
                    "warning": "total_duration_overflow",
                    "message": f"分镜总时长 {total:.1f} 秒超过目标 {limit} 秒",
                    "suggestions": [
                        {"action": "auto_balance", "label": "自动平衡其他分镜"},
                        {"action": "keep_as_is", "label": "保持原样（保存后可手动调整）"},
                    ],
                    "requires_confirmation": True,
                    "frame": self._frame_to_dict(frame),
                }
            self._sync_legacy_fields(frame)
            frame.dirty = 1  # 标记帧已被手动编辑
            frame.version = (frame.version or 1) + 1
            frame.last_edited_at = datetime.utcnow()
            # 旁白溢出检测
            if "narration" in changed_fields and frame.narration:
                estimated_seconds = len(frame.narration) / 3
                current_duration = float(frame.duration or 5)
                if estimated_seconds > current_duration * 1.5:
                    await db.flush()
                    return {
                        "warning": "narration_overflow",
                        "message": (
                            f"旁白约 {len(frame.narration)} 字，需要 {estimated_seconds:.0f} 秒，"
                            f"当前分镜只有 {current_duration} 秒"
                        ),
                        "suggestions": [
                            {"action": "extend_duration", "label": "延长分镜时长", "new_duration": round(estimated_seconds)},
                            {"action": "trim_narration", "label": "精简旁白", "target_chars": int(current_duration * 3)},
                            {"action": "keep_as_is", "label": "保持原样（生成时截断）"},
                        ],
                        "requires_confirmation": True,
                        "frame": self._frame_to_dict(frame),
                    }
            # narration 修改标记 TTS dirty
            if "narration" in changed_fields:
                ai_params = dict(frame.ai_params or {})
                ai_params["tts_dirty"] = True
                frame.ai_params = ai_params
            dirty_stage = self._infer_dirty_stage(changed_fields)
            if project:
                generation_workflow_service.invalidate_from(project, dirty_stage)
            await self._sync_project_script_snapshot(db, project, frames)
            await db.commit()
            await db.refresh(frame)

        return self._frame_to_dict(frame)

    def _sync_legacy_fields(self, frame: Frame) -> None:
        """将新字段同步到旧版兼容字段，确保旧逻辑读取时数据一致。"""
        frame.description = frame.image_prompt or frame.description
        frame.prompt = frame.video_prompt or frame.prompt
        frame.text_overlay = frame.subtitle_text or frame.text_overlay
        ai_params = dict(frame.ai_params or {})
        if frame.narration is not None:
            ai_params["text"] = frame.narration
        if frame.subtitle_position is not None:
            ai_params["overlay_position"] = frame.subtitle_position
        frame.ai_params = ai_params

    def _infer_dirty_stage(self, changed_fields: set[str]) -> str:
        """Infer the earliest invalid workflow stage from edited frame fields."""
        if not changed_fields:
            return "script"
        if "sequence" in changed_fields:
            return "script"
        if "image_prompt" in changed_fields:
            return "image"
        if "video_prompt" in changed_fields or "duration" in changed_fields:
            return "video"
        if (
            "narration" in changed_fields
            or "subtitle_text" in changed_fields
            or "subtitle_position" in changed_fields
        ):
            return "video"
        return "script"

    async def _sync_project_script_snapshot(
        self,
        db: AsyncSession,
        project: Project | None,
        frames: list[Frame],
    ) -> Script | None:
        """Persist a latest script snapshot derived from current frame values."""
        if not project:
            return None

        latest_result = await db.execute(
            select(Script)
            .where(Script.project_id == project.id)
            .order_by(Script.version.desc())
            .limit(1)
        )
        latest_script = latest_result.scalar_one_or_none()
        if not latest_script:
            return None

        version_result = await db.execute(
            select(func.max(Script.version)).where(Script.project_id == project.id)
        )
        max_version = version_result.scalar_one() or latest_script.version or 1
        next_version = int(max_version) + 1

        ordered_frames = sorted(frames, key=lambda item: (item.sequence or 0, item.id or 0))
        content = self._build_script_content_from_frames(project, latest_script.content or {}, ordered_frames)
        new_script = Script(
            project_id=project.id,
            version=next_version,
            status="active",
            generation_mode="storyboard_edit",
            template_id=latest_script.template_id,
            strategy_id=latest_script.strategy_id,
            used_factors=latest_script.used_factors,
            template_params=latest_script.template_params,
            prompt_snapshot={
                **(latest_script.prompt_snapshot or {}),
                "source": "storyboard_edit",
                "updated_at": datetime.utcnow().isoformat(),
            },
            rag_snapshot=latest_script.rag_snapshot,
            content=content,
            parent_id=latest_script.id,
        )
        db.add(new_script)
        await db.flush()
        for item in ordered_frames:
            item.script_id = new_script.id
        return new_script

    def _build_script_content_from_frames(
        self,
        project: Project,
        latest_content: dict[str, Any],
        frames: list[Frame],
    ) -> dict[str, Any]:
        """Rebuild editable script content from current frame values."""
        video_meta = dict((latest_content or {}).get("video_meta") or {})
        if project.title:
            video_meta.setdefault("product_name", project.title)
        if project.target_duration:
            video_meta["target_duration"] = project.target_duration
        if project.style:
            video_meta.setdefault("style", project.style)

        audio = dict((latest_content or {}).get("audio") or {})
        if project.voice_type:
            audio["tts_voice"] = project.voice_type

        scenes = []
        for index, frame in enumerate(frames, 1):
            ai_params = dict(frame.ai_params or {})
            metadata = dict(frame.metadata_ or {})
            scenes.append({
                "scene_id": index,
                "type": metadata.get("scene_type_str") or "",
                "duration": float(frame.duration) if isinstance(frame.duration, Decimal) else frame.duration,
                "text": frame.narration or "",
                "voice_style": ai_params.get("voice_style", ""),
                "visual": {
                    "image_prompt": frame.image_prompt or frame.description or "",
                    "video_prompt": frame.video_prompt or frame.prompt or "",
                    "camera": ai_params.get("camera", ""),
                    "mood": ai_params.get("mood", ""),
                    "overlay": {
                        "text": frame.subtitle_text or frame.text_overlay or "",
                        "position": frame.subtitle_position or ai_params.get("overlay_position", "bottom"),
                        "style": ai_params.get("overlay_style", "highlight"),
                    },
                },
            })

        return {
            "video_meta": video_meta,
            "scenes": scenes,
            "audio": audio,
        }

    def _script_to_dict(self, script: Script, *, include_content: bool) -> dict[str, Any]:
        """将 Script 模型转为字典。include_content=False 时省略 LLM 输出等大字段。"""
        data = {
            "id": script.id,
            "project_id": script.project_id,
            "version": script.version,
            "status": script.status,
            "generation_mode": script.generation_mode,
            "parent_id": script.parent_id,
            "created_at": script.created_at.isoformat() if script.created_at else None,
        }
        if include_content:
            data.update({
                "prompt_snapshot": script.prompt_snapshot,
                "rag_snapshot": script.rag_snapshot,
                "content": script.content,
            })
        return data

    def _frame_to_dict(self, frame: Frame) -> dict[str, Any]:
        """将 Frame 模型转为 API 响应字典。"""
        return {
            "id": frame.id,
            "project_id": frame.project_id,
            "script_id": frame.script_id,
            "sequence": frame.sequence,
            "scene_type": frame.scene_type,
            "description": frame.description,
            "prompt": frame.prompt,
            "narration": frame.narration,
            "subtitle_text": frame.subtitle_text,
            "subtitle_position": frame.subtitle_position,
            "image_prompt": frame.image_prompt,
            "video_prompt": frame.video_prompt,
            "text_overlay": frame.text_overlay,
            "duration": float(frame.duration) if isinstance(frame.duration, Decimal) else frame.duration,
            "status": frame.status,
            "dirty": bool(frame.dirty),
            "last_edited_at": frame.last_edited_at.isoformat() if frame.last_edited_at else None,
            "image_url": frame.image_url,
            "audio_url": frame.audio_url,
            "video_url": frame.video_url,
            "error_message": frame.error_message,
            "ai_params": frame.ai_params,
        }


storyboard_service = StoryboardService()
