"""
对话驱动视频生成Agent - 基于ReAct范式
放在generate业务包下，使用agent框架包的ReAct能力

职责：图片生成、视频生成、分镜编辑、对话
不包含：剧本生成（由子agent负责）

替代：llm_agent_service + workflow_agent_service 的意图识别功能
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.v1.app.agent import ReActAgent, BaseTool
from backend.v1.app.generate.service.stages.image_workflow import image_workflow_service
from backend.v1.app.generate.service.stages.video_workflow import video_generation_service
from backend.v1.app.generate.service.workflow.state import generation_workflow_service

logger = logging.getLogger(__name__)


# ============ 工具定义 ============


class GenerateImagesTool(BaseTool):
    """生成图片工具"""
    name = "generate_images"
    description = "Generate images for all frames. Use when user confirms script, requests images, or says 'continue'."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"}
        },
        "required": ["project_id"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        project_id = parameters["project_id"]

        async def _run():
            async with self.db_session_factory() as db:
                result = await image_workflow_service.submit_image_task(db, project_id)
                return {"success": True, "task_id": result.get("task_id"), "status": result.get("status")}

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            logger.error(f"图片生成失败: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class GenerateVideoTool(BaseTool):
    """生成视频工具"""
    name = "generate_video"
    description = "Generate video for the project. Use when user confirms images or requests video."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"}
        },
        "required": ["project_id"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        project_id = parameters["project_id"]

        async def _run():
            async with self.db_session_factory() as db:
                result = await video_generation_service.submit_generation_task(db, project_id)
                return {"success": True, "task_id": result.get("task_id"), "status": result.get("status")}

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            logger.error(f"视频生成失败: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class EditFrameTool(BaseTool):
    """编辑分镜工具"""
    name = "edit_frame"
    description = "Edit frame content (description, narration, image_prompt, etc). Use when user wants to modify a frame."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"},
            "frame_id": {"type": "integer", "description": "分镜ID"},
            "field": {"type": "string", "description": "要修改的字段", "enum": ["description", "narration", "image_prompt", "video_prompt"]},
            "value": {"type": "string", "description": "新值"}
        },
        "required": ["project_id", "frame_id", "field", "value"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        from sqlalchemy import select
        from backend.v1.app.models.frame import Frame
        from backend.v1.app.models.project import Project

        project_id = parameters["project_id"]
        frame_id = parameters["frame_id"]
        field = parameters["field"]
        value = parameters["value"]

        async def _run():
            async with self.db_session_factory() as db:
                result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
                frame = result.scalar_one_or_none()
                if not frame:
                    return {"success": False, "error": f"分镜不存在: {frame_id}"}

                if hasattr(frame, field):
                    setattr(frame, field, value)
                    frame.dirty = 1

                    # 标记工作流失效
                    proj_result = await db.execute(select(Project).where(Project.id == project_id))
                    project = proj_result.scalar_one_or_none()
                    if project:
                        generation_workflow_service.invalidate_from(project, "image")

                    await db.commit()
                    return {"success": True, "message": f"分镜{frame_id}的{field}已更新"}
                return {"success": False, "error": f"无效字段: {field}"}

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            logger.error(f"分镜编辑失败: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class RegenerateFrameImageTool(BaseTool):
    """重新生成单个分镜图片"""
    name = "regenerate_frame_image"
    description = "Regenerate image for a specific frame. Use when user is not satisfied with an image."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"},
            "frame_id": {"type": "integer", "description": "分镜ID"}
        },
        "required": ["project_id", "frame_id"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        from sqlalchemy import select
        from backend.v1.app.models.frame import Frame
        from backend.v1.app.models.project import Project
        from backend.v1.app.generate.tasks.celery_app import celery_app
        from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service

        project_id = parameters["project_id"]
        frame_id = parameters["frame_id"]

        async def _run():
            async with self.db_session_factory() as db:
                result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
                frame = result.scalar_one_or_none()
                if not frame:
                    return {"success": False, "error": f"分镜不存在: {frame_id}"}

                # 标记图片需要重新生成
                frame.image_url = None
                frame.status = 0
                frame.dirty = 1

                proj_result = await db.execute(select(Project).where(Project.id == project_id))
                project = proj_result.scalar_one_or_none()
                if project:
                    generation_workflow_service.invalidate_from(project, "image")

                await db.commit()

                # 提交图片生成任务
                task = await generation_task_service.create_task(db, project_id, "frame_image", status="queued")
                sent = celery_app.send_task("generate_frame_image_task", args=[project_id, frame_id, task.id])
                await generation_task_service.set_celery_task_id(db, task.id, sent.id)

                return {"success": True, "task_id": task.id, "message": f"分镜{frame_id}图片重生成已提交"}

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            logger.error(f"图片重生成失败: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class RegenerateFrameVideoTool(BaseTool):
    """重新生成单个分镜视频"""
    name = "regenerate_frame_video"
    description = "Regenerate video for a specific frame. Use when user is not satisfied with a video clip."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"},
            "frame_id": {"type": "integer", "description": "分镜ID"}
        },
        "required": ["project_id", "frame_id"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        from sqlalchemy import select
        from backend.v1.app.models.frame import Frame
        from backend.v1.app.models.project import Project
        from backend.v1.app.generate.tasks.celery_app import celery_app
        from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service

        project_id = parameters["project_id"]
        frame_id = parameters["frame_id"]

        async def _run():
            async with self.db_session_factory() as db:
                result = await db.execute(select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id))
                frame = result.scalar_one_or_none()
                if not frame:
                    return {"success": False, "error": f"分镜不存在: {frame_id}"}

                frame.dirty = 1

                proj_result = await db.execute(select(Project).where(Project.id == project_id))
                project = proj_result.scalar_one_or_none()
                if project:
                    generation_workflow_service.invalidate_from(project, "video")

                await db.commit()

                task = await generation_task_service.create_task(db, project_id, "frame_video", status="queued")
                sent = celery_app.send_task("generate_frame_video_task", args=[project_id, frame_id, task.id])
                await generation_task_service.set_celery_task_id(db, task.id, sent.id)

                return {"success": True, "task_id": task.id, "message": f"分镜{frame_id}视频重生成已提交"}

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            logger.error(f"视频重生成失败: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


class QueryProjectStatusTool(BaseTool):
    """查询项目状态工具"""
    name = "query_status"
    description = "Query project status including workflow stage and frame info. Use when unsure about current state."
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "项目ID"}
        },
        "required": ["project_id"]
    }

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    def execute(self, parameters: Dict[str, Any]) -> str:
        import asyncio
        from sqlalchemy import select
        from backend.v1.app.models.project import Project
        from backend.v1.app.models.frame import Frame

        project_id = parameters["project_id"]

        async def _run():
            async with self.db_session_factory() as db:
                proj_result = await db.execute(select(Project).where(Project.id == project_id))
                project = proj_result.scalar_one_or_none()
                if not project:
                    return {"success": False, "error": "项目不存在"}

                frame_result = await db.execute(
                    select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence)
                )
                frames = frame_result.scalars().all()

                return {
                    "success": True,
                    "workflow_stage": project.workflow_stage,
                    "stage_status": project.stage_status,
                    "dirty_stage": project.dirty_stage,
                    "frames_count": len(frames),
                    "frames": [
                        {
                            "id": f.id,
                            "sequence": f.sequence,
                            "description": (f.description or "")[:80],
                            "status": f.status,
                            "dirty": bool(f.dirty),
                            "has_image": bool(f.image_url),
                            "has_video": bool(f.video_url),
                        }
                        for f in frames
                    ]
                }

        try:
            return json.dumps(asyncio.run(_run()), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ============ Agent系统提示 ============

VIDEO_AGENT_SYSTEM_PROMPT = """你是「带货视频生成系统」的AI助手，负责帮助用户完成视频生成流程。

## 当前项目状态
{project_status}

## 你的职责
通过对话理解用户意图，调用合适的工具完成操作。

## 可用工具
1. **query_status** - 查询项目状态（不确定时先查询）
2. **generate_images** - 生成分镜图片（剧本完成后）
3. **generate_video** - 生成视频成片（图片确认后）
4. **edit_frame** - 修改分镜内容
5. **regenerate_frame_image** - 重新生成某张图片
6. **regenerate_frame_video** - 重新生成某个视频片段

## 决策规则
1. **确认推进**: 用户说"确认"、"可以"、"继续"、"下一步"时，根据当前阶段推进：
   - script阶段 → generate_images
   - image阶段 → generate_video
2. **修改内容**: 用户要求修改分镜描述/旁白/提示词 → edit_frame
3. **重生成**: 用户对某张图/视频不满意 → regenerate_frame_image/video
4. **普通对话**: 其他情况直接回复，不调用工具

## 重要原则
- 涉及生成操作时，先确认用户意图
- 不确定项目状态时，先用query_status查询
- 回复要简洁友好，用中文
"""


# ============ Agent定义 ============

class ReactVideoAgent(ReActAgent):
    """
    基于ReAct范式的视频生成Agent

    替代原有的 llm_agent_service + workflow_agent_service 组合，
    通过ReAct循环自动完成意图识别和工具调用。

    不包含剧本生成（由子agent负责）。
    """

    def __init__(
        self,
        agent_id: str = "react_video_agent",
        name: str = "视频生成助手",
        db_session_factory=None,
        **kwargs
    ):
        super().__init__(agent_id=agent_id, name=name, **kwargs)
        self.db_session_factory = db_session_factory
        self._register_tools()

    def _register_tools(self):
        """注册业务工具"""
        factory = self.db_session_factory
        self.tool_system.register_tool(GenerateImagesTool(factory))
        self.tool_system.register_tool(GenerateVideoTool(factory))
        self.tool_system.register_tool(EditFrameTool(factory))
        self.tool_system.register_tool(RegenerateFrameImageTool(factory))
        self.tool_system.register_tool(RegenerateFrameVideoTool(factory))
        self.tool_system.register_tool(QueryProjectStatusTool(factory))

    def _get_project_status_text(self, context: Optional[Dict[str, Any]]) -> str:
        """从context获取项目状态文本"""
        if not context:
            return "未知"

        stage = context.get("workflow_stage", "unknown")
        status = context.get("stage_status", "unknown")
        frames_count = context.get("frames_count", 0)

        stage_names = {
            "created": "待生成剧本",
            "script": "剧本阶段",
            "image": "图片阶段",
            "video": "视频阶段",
            "completed": "已完成"
        }

        status_names = {
            "idle": "空闲",
            "running": "运行中",
            "awaiting_review": "待确认",
            "confirmed": "已确认",
            "failed": "失败"
        }

        return f"阶段: {stage_names.get(stage, stage)} | 状态: {status_names.get(status, status)} | 分镜数: {frames_count}"

    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """重写run方法，注入项目状态到系统提示"""
        project_id = (context or {}).get("project_id")

        # 构建带项目状态的查询
        if project_id:
            status_text = self._get_project_status_text(context)
            enhanced_query = f"[项目ID: {project_id} | {status_text}]\n{query}"
        else:
            enhanced_query = query

        return super().run(enhanced_query, context)
