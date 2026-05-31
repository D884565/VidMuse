"""分镜编辑服务 — 管理剧本版本和分镜帧的编辑操作。"""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script
from backend.v1.app.generate.service.workflow.state import generation_workflow_service
from backend.v1.app.generate.service.workflow.limits import validate_total_frame_duration

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
        for field, value in patch.items():
            if field not in EDITABLE_FRAME_FIELDS:
                continue
            setattr(frame, field, value)
            changed = True

        if changed:
            project = await db.get(Project, project_id)
            duration_result = await db.execute(select(Frame).where(Frame.project_id == project_id))
            frames = list(duration_result.scalars().all())
            validate_total_frame_duration(
                [item.duration for item in frames],
                target_duration=project.target_duration if project else None,
            )
            self._sync_legacy_fields(frame)
            frame.dirty = 1  # 标记帧已被手动编辑
            frame.last_edited_at = datetime.utcnow()
            # 编辑后将项目状态置为"待审核"，需重新渲染才能生效
            if project:
                generation_workflow_service.invalidate_from(project, "script")
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
