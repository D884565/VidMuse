"""链路追踪管理业务逻辑层

职责：处理链路追踪相关的业务逻辑，包括查询、统计、数据转换等。
不直接操作数据库，通过 TraceManagementDAO 访问数据层。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from backend.framework.exceptions.exceptions import NotFoundException
from backend.framework.exceptions.error_codes import RESOURCE_NOT_FOUND
from ..dao.trace_management_dao import trace_management_dao
from ..dto.trace_management_schema import (
    TraceBase,
    TraceDetail,
    SpanBase,
    SpanDetail,
    TraceListResponse,
    SpanListResponse,
    TraceStatResponse
)


class TraceManagementService:
    """链路追踪管理业务逻辑层"""

    @staticmethod
    def _build_span_tree(spans: List[Any], parent_id: Optional[str] = None) -> List[SpanDetail]:
        """构建Span树形结构

        :param spans: Span列表
        :param parent_id: 父Span ID
        :return: 树形结构的Span列表
        """
        # 转换为字典，按span_id索引 - 提前准备所有必填字段，避免验证失败
        span_dict = {}
        for span in spans:
            span_data = {
                **span.__dict__,
                "has_exception": span.exception is not None,
                "child_spans": []
            }
            span_detail = SpanDetail.model_validate(span_data)
            span_dict[span.span_id] = span_detail

        # 构建树形结构
        tree = []
        for span in span_dict.values():
            if span.parent_span_id == parent_id:
                tree.append(span)
            else:
                parent_span = span_dict.get(span.parent_span_id)
                if parent_span:
                    parent_span.child_spans.append(span)

        return tree

    @staticmethod
    def list_traces(
        db: Session,
        trace_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        client_ip: Optional[str] = None,
        user_id: Optional[int] = None,
        has_exception: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> TraceListResponse:
        """分页查询Trace列表

        :param db: 数据库会话
        :param trace_id: 按链路ID筛选（可选）
        :param method: 按HTTP方法筛选（可选）
        :param path: 按请求路径模糊匹配（可选）
        :param status_code: 按响应状态码筛选（可选）
        :param min_duration: 最小耗时(毫秒)（可选）
        :param max_duration: 最大耗时(毫秒)（可选）
        :param client_ip: 按客户端IP筛选（可选）
        :param user_id: 按用户ID筛选（可选）
        :param has_exception: 是否包含异常（可选）
        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param page: 页码
        :param page_size: 每页数量
        :return: Trace列表响应DTO
        """
        total, traces = trace_management_dao.list_traces(
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

        # 转换为基础DTO
        trace_list = []
        for trace in traces:
            trace_base = TraceBase.model_validate(trace)
            trace_list.append(trace_base)

        return TraceListResponse(
            total=total,
            page=page,
            page_size=page_size,
            list=trace_list
        )

    @staticmethod
    def get_trace_detail(db: Session, trace_id: int) -> TraceDetail:
        """获取Trace详情

        :param db: 数据库会话
        :param trace_id: Trace ID
        :return: Trace详情DTO
        """
        trace = trace_management_dao.get_trace_by_id(db, trace_id)
        if not trace:
            raise NotFoundException(RESOURCE_NOT_FOUND, f"Trace ID {trace_id} 不存在")

        # 获取关联的Span统计（确保始终返回有效值，避免None）
        span_count = trace_management_dao.get_span_count_by_trace_id(db, trace.trace_id) or 0
        total_span_duration = trace_management_dao.get_total_span_duration_by_trace_id(db, trace.trace_id) or 0.0

        # 转换为详情DTO - 先验证基础字段，再添加统计字段，避免必填字段校验失败
        trace_base = TraceBase.model_validate(trace)
        trace_detail = TraceDetail(
            **trace_base.model_dump(),
            span_count=span_count,
            total_span_duration=float(total_span_duration)
        )

        return trace_detail

    @staticmethod
    def get_trace_spans(
        db: Session,
        trace_id: int,
        include_tree: bool = True,
        include_details: bool = False
    ) -> SpanListResponse:
        """获取Trace下的所有Span

        :param db: 数据库会话
        :param trace_id: Trace ID
        :param include_tree: 是否返回树形结构
        :param include_details: 是否包含详细信息
        :return: Span列表响应DTO
        """
        trace = trace_management_dao.get_trace_by_id(db, trace_id)
        if not trace:
            raise NotFoundException(RESOURCE_NOT_FOUND, f"Trace ID {trace_id} 不存在")

        spans = trace_management_dao.get_spans_by_trace_id(
            db=db,
            trace_id=trace.trace_id,
            include_details=include_details
        )

        total = len(spans)

        # 转换为基础DTO - 提前准备所有必填字段，避免验证失败
        span_list = []
        for span in spans:
            # 先转换基础字段，再添加has_exception字段
            span_data = {
                **span.__dict__,
                "has_exception": span.exception is not None
            }
            span_base = SpanBase.model_validate(span_data)
            span_list.append(span_base)

        # 构建树形结构
        span_tree = None
        if include_tree and include_details:
            span_tree = TraceManagementService._build_span_tree(spans)

        return SpanListResponse(
            trace_id=trace.trace_id,
            total=total,
            list=span_list,
            tree=span_tree
        )

    @staticmethod
    def get_span_detail(db: Session, span_id: int) -> SpanDetail:
        """获取Span详情

        :param db: 数据库会话
        :param span_id: Span ID
        :return: Span详情DTO
        """
        span = trace_management_dao.get_span_by_id(db, span_id)
        if not span:
            raise NotFoundException(RESOURCE_NOT_FOUND, f"Span ID {span_id} 不存在")

        # 转换为详情DTO - 提前准备所有必填字段，避免验证失败
        span_data = {
            **span.__dict__,
            "has_exception": span.exception is not None
        }
        span_detail = SpanDetail.model_validate(span_data)

        # 查询子Span - 转换时添加必填字段
        child_spans = trace_management_dao.get_child_spans(db, span.trace_id, span.span_id)
        span_detail.child_spans = []
        for child in child_spans:
            child_data = {
                **child.__dict__,
                "has_exception": child.exception is not None,
                "child_spans": []
            }
            child_detail = SpanDetail.model_validate(child_data)
            span_detail.child_spans.append(child_detail)

        return span_detail

    @staticmethod
    def get_statistics(
        db: Session,
        period: str = "7d",
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> TraceStatResponse:
        """获取Trace统计数据

        :param db: 数据库会话
        :param period: 统计周期：1d(最近1天)、7d(最近7天)、30d(最近30天)、all(全部)
        :param user_id: 按用户ID筛选（可选）
        :param start_time: 自定义开始时间（可选）
        :param end_time: 自定义结束时间（可选）
        :return: 统计响应DTO
        """
        stat = trace_management_dao.get_statistics(
            db=db,
            period=period,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time
        )

        return TraceStatResponse(**stat)


# 全局服务实例
trace_management_service = TraceManagementService()
