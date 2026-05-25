from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend.v1.app.models.project import Project


class ProjectDAO:
    """项目数据访问层"""

    @staticmethod
    def create_project(db: Session, project_data: dict) -> Project:
        """创建项目记录"""
        project = Project(**project_data)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def get_project_by_id(db: Session, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def update_project(db: Session, project_id: int, update_data: dict) -> Optional[Project]:
        """更新项目信息"""
        db.query(Project).filter(Project.id == project_id).update(update_data)
        db.commit()
        return ProjectDAO.get_project_by_id(db, project_id)

    @staticmethod
    def delete_project(db: Session, project_id: int) -> bool:
        """删除项目"""
        result = db.query(Project).filter(Project.id == project_id).delete()
        db.commit()
        return result > 0

    @staticmethod
    def list_projects(
            db: Session,
            user_id: Optional[int] = None,
            status: Optional[int] = None,
            keyword: Optional[str] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            page: int = 1,
            page_size: int = 20
    ) -> tuple[int, list[Project]]:
        """分页查询项目列表"""
        query = db.query(Project)

        # 用户筛选
        if user_id is not None:
            query = query.filter(Project.user_id == user_id)

        # 状态转换：接口的整数状态转换为数据库的字符串状态
        if status is not None:
            status_map = {
                0: "draft",
                1: "processing",
                2: "completed",
                3: "failed"
            }
            db_status = status_map.get(status, "draft")
            query = query.filter(Project.status == db_status)

        # 关键词搜索
        if keyword:
            title_match = Project.title.like(f"%{keyword}%")
            description_match = Project.description.like(f"%{keyword}%")
            query = query.filter(title_match | description_match)

        # 时间范围筛选
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Project.created_at >= start_datetime)

        if end_date:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Project.created_at <= end_datetime)

        total = query.count()

        offset = (page - 1) * page_size
        projects = query.order_by(Project.created_at.desc()).offset(offset).limit(page_size).all()

        return total, projects
