"""项目数据访问层（异步版本）"""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project


class ProjectDAO:
    """项目 DAO - 异步"""

    @staticmethod
    async def create(db: AsyncSession, project_data: dict) -> Project:
        project = Project(**project_data)
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def get_by_id(db: AsyncSession, project_id: int) -> Optional[Project]:
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db: AsyncSession, project_id: int, update_data: dict) -> Optional[Project]:
        project = await ProjectDAO.get_by_id(db, project_id)
        if not project:
            return None
        for key, value in update_data.items():
            if hasattr(project, key):
                setattr(project, key, value)
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def delete(db: AsyncSession, project_id: int) -> bool:
        project = await ProjectDAO.get_by_id(db, project_id)
        if not project:
            return False
        await db.delete(project)
        await db.commit()
        return True

    @staticmethod
    async def list_projects(
        db: AsyncSession,
        user_id: Optional[int] = None,
        status: Optional[str | list[str]] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[tuple[Project, int]]]:
        frame_count_subquery = (
            select(Frame.project_id, func.count(Frame.id).label("frame_count"))
            .group_by(Frame.project_id)
            .subquery()
        )
        query = (
            select(Project, func.coalesce(frame_count_subquery.c.frame_count, 0))
            .outerjoin(frame_count_subquery, frame_count_subquery.c.project_id == Project.id)
        )

        if user_id is not None:
            query = query.where(Project.user_id == user_id)
        if status is not None:
            if isinstance(status, list):
                query = query.where(Project.status.in_(status))
            else:
                query = query.where(Project.status == status)
        if keyword:
            query = query.where(
                Project.title.like(f"%{keyword}%")
                | Project.description.like(f"%{keyword}%")
            )

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.order_by(Project.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        projects = [(row[0], int(row[1] or 0)) for row in result.all()]

        return total, projects
