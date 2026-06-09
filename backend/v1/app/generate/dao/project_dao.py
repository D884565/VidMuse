"""项目数据访问层（异步版本）"""
import logging
from typing import Optional
from sqlalchemy import select, func, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.v1.app.models.frame import Frame
from backend.v1.app.models.project import Project
from backend.v1.app.models.conversation import Conversation
from backend.v1.app.models.script import Script
from backend.v1.app.push.model.message_model import PushMessage, UserMessage

logger = logging.getLogger(__name__)


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
    async def get_by_id(db: AsyncSession, project_id: int, *, eager: bool = False) -> Optional[Project]:
        query = select(Project).where(Project.id == project_id)
        if eager:
            query = query.options(
                selectinload(Project.frames),
                selectinload(Project.conversations),
                selectinload(Project.scripts),
            )
        result = await db.execute(query)
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
        # 先确认项目存在
        exists = await db.execute(select(Project.id).where(Project.id == project_id))
        if not exists.scalar_one_or_none():
            return False

        # ── 显式删除所有关联数据（不依赖 ORM cascade，async 下不可靠）──

        # 1. conversations（核心：用户看到的"对话还存在"就是这张表没删干净）
        await db.execute(sa_delete(Conversation).where(Conversation.project_id == project_id))

        # 2. scripts
        # scripts.parent_id -> scripts.id 是自引用外键。失败项目常有版本链，
        # 先批量断开项目内脚本的 parent_id，再删除脚本，避免整批删除触发 FK 拦截。
        await db.execute(
            sa_update(Script)
            .where(Script.project_id == project_id)
            .values(parent_id=None)
        )
        await db.execute(sa_delete(Script).where(Script.project_id == project_id))

        # 3. frames
        await db.execute(sa_delete(Frame).where(Frame.project_id == project_id))

        # 4. push_messages + user_messages（无 FK 约束）
        msg_ids_result = await db.execute(
            select(PushMessage.message_id).where(PushMessage.project_id == project_id)
        )
        msg_ids = [row[0] for row in msg_ids_result.all()]
        if msg_ids:
            await db.execute(sa_delete(UserMessage).where(UserMessage.message_id.in_(msg_ids)))
        await db.execute(sa_delete(PushMessage).where(PushMessage.project_id == project_id))

        # 5. generation_tasks（无 FK 约束）
        from backend.v1.app.models.generation_task import GenerationTask
        await db.execute(sa_delete(GenerationTask).where(GenerationTask.project_id == project_id))

        # 6. generation_frame_progress（无 FK 约束）
        from backend.v1.app.models.generation_frame_progress import GenerationFrameProgress
        await db.execute(sa_delete(GenerationFrameProgress).where(GenerationFrameProgress.project_id == project_id))

        # 7. agent_traces（无 FK 约束）
        from backend.v1.app.models.agent_trace import AgentTrace
        await db.execute(sa_delete(AgentTrace).where(AgentTrace.project_id == project_id))

        # 8. 最后删除项目本身
        await db.execute(sa_delete(Project).where(Project.id == project_id))

        await db.commit()
        logger.info(f"[ProjectDAO.delete] project_id={project_id} 及所有关联数据已删除")
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
