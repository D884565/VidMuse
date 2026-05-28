"""项目业务逻辑层（异步版本）"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.framework.exceptions.exceptions import BusinessException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND, PARAM_ERROR
from backend.v1.app.generate.dao.project_dao import ProjectDAO


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

        return {
            "list": [_project_to_dict(p) for p in projects],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
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

_STATUS_TO_INT = {
    "draft": 0,
    "script_ready": 1,
    "processing": 2,
    "completed": 3,
    "failed": 4,
}
_INT_TO_STATUS = {0: "draft", 1: "script_ready", 2: "processing", 3: "completed", 4: "failed"}
_STATUS_NAME = {0: "待生成", 1: "剧本就绪", 2: "生成中", 3: "已完成", 4: "失败"}


def _project_to_dict(project) -> dict:
    status_int = _STATUS_TO_INT.get(project.status, 0)
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "product_url": project.product_url,
        "video_output_url": project.video_output_url,
        "audio_url": project.audio_url,
        "user_id": project.user_id,
        "status": status_int,
        "status_name": _STATUS_NAME.get(status_int, "未知"),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
