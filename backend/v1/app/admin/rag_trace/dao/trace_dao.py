"""Agent轨迹数据访问层

职责：封装所有对 agent_traces 表的数据库操作，Service 层通过此层访问数据库。
"""
from typing import Optional, Tuple, List
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from datetime import datetime

from backend.v1.app.models.agent_trace import AgentTrace


class AgentTraceDAO:
    """Agent轨迹数据访问层"""

    @staticmethod
    def get_trace_by_id(db: Session, trace_id: int) -> Optional[AgentTrace]:
        """根据轨迹ID查询详情

        :param db: 数据库会话
        :param trace_id: 轨迹ID
        :return: AgentTrace 对象，不存在返回 None
        """
        return db.query(AgentTrace).filter(AgentTrace.id == trace_id).first()

    @staticmethod
    def get_traces_by_session_id(
        db: Session,
        session_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[AgentTrace]]:
        """根据会话ID查询轨迹列表

        :param db: 数据库会话
        :param session_id: 会话ID
        :param page: 页码
        :param page_size: 每页数量
        :return: (总数量, 轨迹列表)
        """
        query = db.query(AgentTrace).filter(AgentTrace.session_id == session_id)

        # 统计总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        traces = query.order_by(AgentTrace.created_at.desc()) \
            .offset(offset) \
            .limit(page_size) \
            .all()

        return total, traces

    @staticmethod
    def get_traces_by_user_id(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[AgentTrace]]:
        """根据用户ID查询轨迹列表

        :param db: 数据库会话
        :param user_id: 用户ID
        :param page: 页码
        :param page_size: 每页数量
        :return: (总数量, 轨迹列表)
        """
        query = db.query(AgentTrace).filter(AgentTrace.user_id == user_id)

        # 统计总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        traces = query.order_by(AgentTrace.created_at.desc()) \
            .offset(offset) \
            .limit(page_size) \
            .all()

        return total, traces

    @staticmethod
    def list_traces(
        db: Session,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        model: Optional[str] = None,
        success: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[int, List[AgentTrace]]:
        """多条件查询轨迹列表

        :param db: 数据库会话
        :param session_id: 按会话ID筛选（可选）
        :param user_id: 按用户ID筛选（可选）
        :param project_id: 按项目ID筛选（可选）
        :param model: 按模型名称筛选（可选）
        :param success: 按执行结果筛选（可选）
        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param keyword: 关键词搜索（用户输入/回答，可选）
        :param page: 页码
        :param page_size: 每页数量
        :return: (总数量, 轨迹列表)
        """
        query = db.query(AgentTrace)

        # 条件筛选
        filters = []
        if session_id:
            filters.append(AgentTrace.session_id == session_id)
        if user_id is not None:
            filters.append(AgentTrace.user_id == user_id)
        if project_id is not None:
            filters.append(AgentTrace.project_id == project_id)
        if model:
            filters.append(AgentTrace.model == model)
        if success is not None:
            filters.append(AgentTrace.success == success)
        if start_time:
            filters.append(AgentTrace.created_at >= start_time)
        if end_time:
            filters.append(AgentTrace.created_at <= end_time)
        if keyword:
            filters.append(or_(
                AgentTrace.user_input.like(f"%{keyword}%"),
                AgentTrace.final_answer.like(f"%{keyword}%")
            ))

        if filters:
            query = query.filter(and_(*filters))

        # 统计总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        traces = query.order_by(AgentTrace.created_at.desc()) \
            .offset(offset) \
            .limit(page_size) \
            .all()

        return total, traces

    @staticmethod
    def get_statistics(
        db: Session,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None
    ) -> dict:
        """查询轨迹统计数据

        :param db: 数据库会话
        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param user_id: 按用户ID筛选（可选）
        :param project_id: 按项目ID筛选（可选）
        :return: 统计数据字典
        """
        query = db.query(
            func.count(AgentTrace.id).label("total_count"),
            func.sum(AgentTrace.success.cast(int)).label("success_count"),
            func.avg(AgentTrace.cost_time).label("avg_cost_time"),
            func.sum(func.json_length(AgentTrace.tool_calls)).label("total_tool_calls")
        )

        # 条件筛选
        filters = []
        if start_time:
            filters.append(AgentTrace.created_at >= start_time)
        if end_time:
            filters.append(AgentTrace.created_at <= end_time)
        if user_id is not None:
            filters.append(AgentTrace.user_id == user_id)
        if project_id is not None:
            filters.append(AgentTrace.project_id == project_id)

        if filters:
            query = query.filter(and_(*filters))

        stat = query.first()

        total_count = stat.total_count or 0
        success_count = stat.success_count or 0
        avg_cost_time = float(stat.avg_cost_time or 0)
        total_tool_calls = int(stat.total_tool_calls or 0)

        return {
            "total_count": total_count,
            "success_count": success_count,
            "failed_count": total_count - success_count,
            "success_rate": success_count / total_count if total_count > 0 else 0,
            "avg_cost_time": round(avg_cost_time, 3),
            "total_tool_calls": total_tool_calls
        }


# 全局DAO实例
agent_trace_dao = AgentTraceDAO()
