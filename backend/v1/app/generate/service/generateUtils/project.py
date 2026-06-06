"""项目业务逻辑层（异步版本）"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, PARAM_ERROR
from backend.v1.app.generate.dao.project_dao import ProjectDAO
from backend.v1.app.generate.service.chat.entry_intent import classify_no_project_message


class ProjectService:
    """项目 Service - 异步"""

    @staticmethod
    async def get_project(db: AsyncSession, project_id: int) -> dict:
        project = await ProjectDAO.get_by_id(db, project_id)
        if not project:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")
        return _project_to_dict(project)

    @staticmethod
    async def list_projects(
        db: AsyncSession,
        user_id: Optional[int] = None,
        status: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        # 整数状态 -> 字符串状态
        db_status = None
        if status is not None:
            db_status = _INT_TO_STATUS.get(status)

        total, projects = await ProjectDAO.list_projects(
            db=db, user_id=user_id, status=db_status, keyword=keyword, page=page, page_size=page_size
        )

        visible_projects = [
            (p, frame_count)
            for p, frame_count in projects
            if not _is_noise_created_project(p, frame_count=frame_count)
        ]

        return {
            "list": [_project_to_dict(p, frame_count=frame_count) for p, frame_count in visible_projects],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(visible_projects),
                "total_pages": (len(visible_projects) + page_size - 1) // page_size if visible_projects else 0,
            },
        }

    @staticmethod
    async def update_project(db: AsyncSession, project_id: int, update_data: dict) -> dict:
        project = await ProjectDAO.get_by_id(db, project_id)
        if not project:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")

        # 过滤掉 None 值和不允许修改的字段
        allowed_fields = {
            "title", "description", "product_url", "user_prompt",
            "style", "target_audience", "key_points", "avoid",
            "rag_weight", "target_duration", "voice_type", "status",
        }
        data = {k: v for k, v in update_data.items() if v is not None and k in allowed_fields}

        if not data:
            return _project_to_dict(project)

        updated = await ProjectDAO.update(db, project_id, data)
        return _project_to_dict(updated)

    @staticmethod
    async def delete_project(db: AsyncSession, project_id: int) -> None:
        project = await ProjectDAO.get_by_id(db, project_id)
        if not project:
            raise BusinessException(RESOURCE_NOT_FOUND, f"项目不存在: {project_id}")

        success = await ProjectDAO.delete(db, project_id)
        if not success:
            raise BusinessException(PARAM_ERROR, "删除失败")


# ========== 内部工具 ==========

# 旧版 status 字符串 → 整数（仅用于 DAO 列表筛选兼容）
_STATUS_TO_INT = {
    "draft": 0,
    "script_generating": 2,
    "script_ready": 1,
    "review_required": 1,
    "processing": 2,
    "render_queued": 2,
    "rendering": 2,
    "completed": 3,
    "failed": 4,
}
_INT_TO_STATUS = {
    0: "draft",
    1: ["script_ready", "review_required"],
    2: ["script_generating", "processing", "render_queued", "rendering"],
    3: "completed",
    4: "failed",
}
_STATUS_NAME = {0: "待生成", 1: "剧本就绪", 2: "生成中", 3: "已完成", 4: "失败"}


def _derive_status_int(project) -> int:
    """从 workflow_stage/stage_status 推导前端状态整数，不再依赖 project.status。"""
    stage = getattr(project, "workflow_stage", None) or "created"
    stage_status = getattr(project, "stage_status", None) or "idle"

    if stage == "completed":
        return 3
    if stage_status == "failed":
        return 4
    if stage_status in ("running",):
        return 2
    if stage_status in ("awaiting_review", "confirmed"):
        return 1
    # created/idle, script/idle 等待触发状态
    return 0


def _derive_status_name(project, status_int: int) -> str:
    """Return a sidebar-friendly label that preserves the active workflow stage."""
    stage = getattr(project, "workflow_stage", None) or "created"
    stage_status = getattr(project, "stage_status", None) or "idle"

    if stage == "completed":
        return "已完成"
    if stage_status == "failed":
        return "失败"
    if stage_status == "running":
        return {
            "script": "剧本生成中",
            "image": "图片生成中",
            "video": "视频生成中",
        }.get(stage, "生成中")
    if stage_status == "awaiting_review":
        return {
            "script": "剧本就绪",
            "image": "图片待确认",
            "video": "视频待确认",
        }.get(stage, "待确认")
    if stage_status == "confirmed":
        return {
            "script": "剧本已确认",
            "image": "图片已确认",
            "video": "视频已确认",
        }.get(stage, "已确认")
    return _STATUS_NAME.get(status_int, "未知")


def _project_to_dict(project, frame_count: int | None = None) -> dict:
    status_int = _derive_status_int(project)
    safe_frame_count = 0 if frame_count is None else frame_count
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "summary": getattr(project, "summary", None),
        "product_url": project.product_url,
        "video_output_url": project.video_output_url,
        "audio_url": project.audio_url,
        "user_id": project.user_id,
        "status_key": project.status,
        "status": status_int,
        "status_name": _derive_status_name(project, status_int),
        "workflow_stage": getattr(project, "workflow_stage", None),
        "stage_status": getattr(project, "stage_status", None),
        "frame_count": safe_frame_count,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def _is_noise_created_project(project, frame_count: int | None = None) -> bool:
    """Hide legacy projects that were accidentally created from ordinary chat."""
    stage = getattr(project, "workflow_stage", None) or "created"
    stage_status = getattr(project, "stage_status", None) or "idle"
    safe_frame_count = 0 if frame_count is None else frame_count

    if stage != "created" or stage_status != "idle":
        return False
    if safe_frame_count > 0:
        return False
    if getattr(project, "product_url", None) or getattr(project, "video_output_url", None):
        return False
    title = getattr(project, "title", None)
    if isinstance(title, str) and any(word in title for word in ("视频", "短视频", "带货")):
        return False

    text = " ".join(
        part.strip()
        for part in (
            getattr(project, "user_prompt", None),
            getattr(project, "title", None),
            getattr(project, "description", None),
            getattr(project, "summary", None),
        )
        if isinstance(part, str) and part.strip()
    )
    if not text:
        return False

    intent = classify_no_project_message(text)
    return not intent.get("should_create_project", False)
