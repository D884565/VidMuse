"""链路追踪管理路由（后台分析专用）

职责：定义链路追踪系统的后台管理接口，仅允许超级管理员访问。
所有业务逻辑委托给 TraceManagementService，自身不包含业务代码。
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from backend.framework.web.response import Response
from backend.framework.web.auth import admin_required
from backend.store.database.sync_database import get_db
from backend.v1.app.admin.trace_management.dto import (
    TraceListResponse,
    TraceDetail,
    SpanListResponse,
    SpanDetail,
    TraceQueryRequest,
    TraceStatResponse
)
from backend.v1.app.admin.trace_management.service import trace_management_service

router = APIRouter(
    prefix="/admin/traces",
    tags=["【后台】链路追踪管理"],
    dependencies=[Depends(admin_required)]  # 所有接口强制管理员权限
)


@router.get("", response_model=Response[TraceListResponse], summary="分页查询Trace列表")
def list_traces(
    trace_id: Optional[str] = Query(None, description="按链路ID筛选"),
    method: Optional[str] = Query(None, description="按HTTP方法筛选"),
    path: Optional[str] = Query(None, description="按请求路径模糊匹配"),
    status_code: Optional[int] = Query(None, description="按响应状态码筛选"),
    min_duration: Optional[float] = Query(None, description="最小耗时(毫秒)"),
    max_duration: Optional[float] = Query(None, description="最大耗时(毫秒)"),
    client_ip: Optional[str] = Query(None, description="按客户端IP筛选"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    has_exception: Optional[bool] = Query(None, description="是否包含异常"),
    start_time: Optional[datetime] = Query(None, description="开始时间（ISO格式）"),
    end_time: Optional[datetime] = Query(None, description="结束时间（ISO格式）"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量，最大200"),
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】分页查询链路追踪列表，支持多条件筛选"""
    result = trace_management_service.list_traces(
        db=db,
        trace_id=trace_id,
        method=method,
        path=path,
        status_code=status_code,
        min_duration=min_duration,
        max_duration=max_duration,
        client_ip=client_ip,
        user_id=user_id,
        has_exception=has_exception,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )
    return Response.success(data=result)


@router.get("/{trace_id}", response_model=Response[TraceDetail], summary="获取Trace详情")
def get_trace_detail(
    trace_id: int,
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】获取单个Trace的完整详情"""
    result = trace_management_service.get_trace_detail(db, trace_id)
    return Response.success(data=result)


@router.get("/{trace_id}/spans", response_model=Response[SpanListResponse], summary="获取Trace下的所有Span")
def get_trace_spans(
    trace_id: int,
    include_tree: bool = Query(True, description="是否返回树形结构"),
    include_details: bool = Query(False, description="是否包含详细信息（参数、返回值等）"),
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】查询指定Trace下的所有Span，支持树形结构展示"""
    result = trace_management_service.get_trace_spans(db, trace_id, include_tree, include_details)
    return Response.success(data=result)


@router.get("/spans/{span_id}", response_model=Response[SpanDetail], summary="获取Span详情")
def get_span_detail(
    span_id: int,
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】获取单个Span的完整详情，包含子Span信息"""
    result = trace_management_service.get_span_detail(db, span_id)
    return Response.success(data=result)


@router.get("/stats/overview", response_model=Response[TraceStatResponse], summary="获取统计概览")
def get_trace_statistics(
    period: str = Query("7d", description="统计周期：1d(最近1天)、7d(最近7天)、30d(最近30天)、all(全部)"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    start_time: Optional[datetime] = Query(None, description="自定义开始时间（优先于period）"),
    end_time: Optional[datetime] = Query(None, description="自定义结束时间（优先于period）"),
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】获取链路追踪统计数据，包括调用次数、成功率、耗时分布等"""
    result = trace_management_service.get_statistics(db, period, user_id, start_time, end_time)
    return Response.success(data=result)


@router.post("/query", response_model=Response[TraceListResponse], summary="高级查询Trace列表")
def query_traces(
    req: TraceQueryRequest,
    _: int = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """【后台管理】高级多条件查询Trace列表，支持复杂筛选条件"""
    result = trace_management_service.list_traces(
        db=db,
        trace_id=req.trace_id,
        method=req.method,
        path=req.path,
        status_code=req.status_code,
        min_duration=req.min_duration,
        max_duration=req.max_duration,
        client_ip=req.client_ip,
        user_id=req.user_id,
        has_exception=req.has_exception,
        start_time=req.start_time,
        end_time=req.end_time,
        page=req.page,
        page_size=req.page_size
    )
    return Response.success(data=result)
