"""Agent轨迹业务逻辑层

职责：处理Agent轨迹相关的业务逻辑，包括查询、统计、导出等。
不直接操作数据库，通过 AgentTraceDAO 访问数据层。
"""
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.framework.exceptions.exceptions import NotFoundException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND
from .dao.trace_dao import agent_trace_dao
from .dto.trace_schema import AgentTraceBase, AgentTraceDetail, AgentTraceListResponse, TraceStatResponse


class AgentTraceService:
    """Agent轨迹业务逻辑层"""

    @staticmethod
    def get_trace_detail(db: Session, trace_id: int) -> AgentTraceDetail:
        """获取轨迹详情

        :param db: 数据库会话
        :param trace_id: 轨迹ID
        :return: 轨迹详情DTO
        """
        trace = agent_trace_dao.get_trace_by_id(db, trace_id)
        if not trace:
            raise NotFoundException(RESOURCE_NOT_FOUND, f"轨迹ID {trace_id} 不存在")

        return AgentTraceDetail.model_validate(trace)

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
    ) -> AgentTraceListResponse:
        """分页查询轨迹列表

        :param db: 数据库会话
        :param session_id: 按会话ID筛选（可选）
        :param user_id: 按用户ID筛选（可选）
        :param project_id: 按项目ID筛选（可选）
        :param model: 按模型名称筛选（可选）
        :param success: 按执行结果筛选（可选）
        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param keyword: 关键词搜索（可选）
        :param page: 页码
        :param page_size: 每页数量
        :return: 轨迹列表响应DTO
        """
        total, traces = agent_trace_dao.list_traces(
            db=db,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            model=model,
            success=success,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            page=page,
            page_size=page_size
        )

        # 转换为基础DTO
        trace_list = [AgentTraceBase.model_validate(trace) for trace in traces]

        return AgentTraceListResponse(
            total=total,
            page=page,
            page_size=page_size,
            list=trace_list
        )

    @staticmethod
    def get_traces_by_session(
        db: Session,
        session_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> AgentTraceListResponse:
        """根据会话ID查询轨迹列表

        :param db: 数据库会话
        :param session_id: 会话ID
        :param page: 页码
        :param page_size: 每页数量
        :return: 轨迹列表响应DTO
        """
        total, traces = agent_trace_dao.get_traces_by_session_id(
            db=db,
            session_id=session_id,
            page=page,
            page_size=page_size
        )

        trace_list = [AgentTraceBase.model_validate(trace) for trace in traces]

        return AgentTraceListResponse(
            total=total,
            page=page,
            page_size=page_size,
            list=trace_list
        )

    @staticmethod
    def get_traces_by_user(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> AgentTraceListResponse:
        """根据用户ID查询轨迹列表

        :param db: 数据库会话
        :param user_id: 用户ID
        :param page: 页码
        :param page_size: 每页数量
        :return: 轨迹列表响应DTO
        """
        total, traces = agent_trace_dao.get_traces_by_user_id(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size
        )

        trace_list = [AgentTraceBase.model_validate(trace) for trace in traces]

        return AgentTraceListResponse(
            total=total,
            page=page,
            page_size=page_size,
            list=trace_list
        )

    @staticmethod
    def get_statistics(
        db: Session,
        period: str = "7d",
        user_id: Optional[int] = None,
        project_id: Optional[int] = None
    ) -> TraceStatResponse:
        """获取轨迹统计数据

        :param db: 数据库会话
        :param period: 统计周期：1d（最近1天）、7d（最近7天）、30d（最近30天）、all（全部）
        :param user_id: 按用户ID筛选（可选）
        :param project_id: 按项目ID筛选（可选）
        :return: 统计响应DTO
        """
        # 计算时间范围
        end_time = datetime.now()
        if period == "1d":
            start_time = end_time - timedelta(days=1)
            period_desc = "最近1天"
        elif period == "7d":
            start_time = end_time - timedelta(days=7)
            period_desc = "最近7天"
        elif period == "30d":
            start_time = end_time - timedelta(days=30)
            period_desc = "最近30天"
        elif period == "all":
            start_time = None
            period_desc = "全部"
        else:
            # 默认7天
            start_time = end_time - timedelta(days=7)
            period_desc = "最近7天"

        # 查询统计数据
        stat = agent_trace_dao.get_statistics(
            db=db,
            start_time=start_time,
            end_time=end_time,
            user_id=user_id,
            project_id=project_id
        )

        return TraceStatResponse(
            **stat,
            period=period_desc
        )


# 全局服务实例
agent_trace_service = AgentTraceService()
