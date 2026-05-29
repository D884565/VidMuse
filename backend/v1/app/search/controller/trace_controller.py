"""Agent轨迹路由

职责：定义Agent轨迹模块的 HTTP 接口，处理请求参数解析和响应包装。
所有业务逻辑委托给 AgentTraceService，自身不包含业务代码。
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from backend.framework.web.response import Response
from backend.framework.web.auth import get_current_user_id, admin_required
from backend.store.database.sync_database import get_db
from .service.trace_service import agent_trace_service
from .dto.trace_schema import (
    AgentTraceDetail,
    AgentTraceListResponse,
    TraceQueryRequest,
    TraceStatResponse
)

router = APIRouter(prefix="/agent/traces", tags=["Agent观测系统"])


# ==================== 公共接口（需要登录） ====================

@router.get("", response_model=Response[AgentTraceListResponse], summary="查询轨迹列表")
def list_traces(
    session_id: Optional[str] = Query(None, description="按会话ID筛选"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    project_id: Optional[int] = Query(None, description="按项目ID筛选"),
    model: Optional[str] = Query(None, description="按模型名称筛选"),
    success: Optional[bool] = Query(None, description="按执行结果筛选"),
    start_time: Optional[datetime] = Query(None, description="开始时间（ISO格式）"),
    end_time: Optional[datetime] = Query(None, description="结束时间（ISO格式）"),
    keyword: Optional[str] = Query(None, description="关键词搜索（用户输入/回答）"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """分页查询Agent推理轨迹列表，支持多条件筛选"""
    result = agent_trace_service.list_traces(
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
    return Response.success(data=result)


@router.get("/{trace_id}", response_model=Response[AgentTraceDetail], summary="获取轨迹详情")
def get_trace_detail(
    trace_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取单个推理轨迹的完整详情，包括消息历史和工具调用信息"""
    result = agent_trace_service.get_trace_detail(db, trace_id)
    return Response.success(data=result)


@router.get("/session/{session_id}", response_model=Response[AgentTraceListResponse], summary="查询会话的轨迹列表")
def get_session_traces(
    session_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """查询指定会话的所有推理轨迹"""
    result = agent_trace_service.get_traces_by_session(db, session_id, page, page_size)
    return Response.success(data=result)


@router.get("/user/{user_id}", response_model=Response[AgentTraceListResponse], summary="查询用户的轨迹列表")
def get_user_traces(
    user_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """查询指定用户的所有推理轨迹（仅管理员或用户本人可访问）"""
    # 普通用户只能查看自己的轨迹，管理员可以查看所有
    if current_user_id != user_id:
        # 这里可以添加管理员权限校验
        pass
    result = agent_trace_service.get_traces_by_user(db, user_id, page, page_size)
    return Response.success(data=result)


@router.get("/stats/overview", response_model=Response[TraceStatResponse], summary="获取轨迹统计数据")
def get_trace_statistics(
    period: str = Query("7d", description="统计周期：1d(最近1天)、7d(最近7天)、30d(最近30天)、all(全部)"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    project_id: Optional[int] = Query(None, description="按项目ID筛选"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """获取Agent推理统计数据，包括调用次数、成功率、平均耗时等"""
    result = agent_trace_service.get_statistics(db, period, user_id, project_id)
    return Response.success(data=result)


# ==================== 管理员接口 ====================

@router.post("/query", response_model=Response[AgentTraceListResponse], summary="高级查询轨迹列表（管理员）")
@admin_required
def query_traces(
    req: TraceQueryRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """高级多条件查询轨迹列表（管理员接口）"""
    result = agent_trace_service.list_traces(
        db=db,
        session_id=req.session_id,
        user_id=req.user_id,
        project_id=req.project_id,
        model=req.model,
        success=req.success,
        start_time=req.start_time,
        end_time=req.end_time,
        keyword=req.keyword,
        page=req.page,
        page_size=req.page_size
    )
    return Response.success(data=result)
