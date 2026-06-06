"""链路追踪管理数据访问层

职责：封装所有对 traces 和 spans 表的数据库查询操作，Service 层通过此层访问数据库。
"""
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import func, and_, or_, text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from backend.framework.trace.models import Trace, Span


class TraceManagementDAO:
    """链路追踪管理数据访问层"""

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
    ) -> Tuple[int, List[Trace]]:
        """多条件查询Trace列表

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
        :return: (总数量, Trace列表)
        """
        query = db.query(Trace)

        # 条件筛选
        filters = []
        if trace_id:
            filters.append(Trace.trace_id == trace_id)
        if method:
            filters.append(Trace.method == method.upper())
        if path:
            filters.append(Trace.path.like(f"%{path}%"))
        if status_code is not None:
            filters.append(Trace.status_code == status_code)
        if min_duration is not None:
            filters.append(Trace.duration_ms >= min_duration)
        if max_duration is not None:
            filters.append(Trace.duration_ms <= max_duration)
        if client_ip:
            filters.append(Trace.client_ip == client_ip)
        if user_id is not None:
            filters.append(Trace.user_id == user_id)
        if has_exception is not None:
            if has_exception:
                filters.append(Trace.id.in_(
                    db.query(Span.trace_id).filter(Span.exception.isnot(None)).distinct()
                ))
            else:
                filters.append(~Trace.id.in_(
                    db.query(Span.trace_id).filter(Span.exception.isnot(None)).distinct()
                ))
        if start_time:
            filters.append(Trace.created_at >= start_time)
        if end_time:
            filters.append(Trace.created_at <= end_time)

        if filters:
            query = query.filter(and_(*filters))

        # 统计总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        traces = query.order_by(Trace.created_at.desc()) \
            .offset(offset) \
            .limit(page_size) \
            .all()

        return total, traces

    @staticmethod
    def get_trace_by_id(db: Session, trace_id: int) -> Optional[Trace]:
        """根据Trace ID查询详情

        :param db: 数据库会话
        :param trace_id: Trace ID
        :return: Trace 对象，不存在返回 None
        """
        return db.query(Trace).filter(Trace.id == trace_id).first()

    @staticmethod
    def get_trace_by_trace_id(db: Session, trace_id_str: str) -> Optional[Trace]:
        """根据trace_id字符串查询详情

        :param db: 数据库会话
        :param trace_id_str: 链路唯一标识
        :return: Trace 对象，不存在返回 None
        """
        return db.query(Trace).filter(Trace.trace_id == trace_id_str).first()

    @staticmethod
    def get_spans_by_trace_id(
        db: Session,
        trace_id: str,
        include_details: bool = False
    ) -> List[Span]:
        """根据trace_id查询所有关联的Span

        :param db: 数据库会话
        :param trace_id: 链路唯一标识
        :param include_details: 是否包含详细信息（参数、返回值、异常等）
        :return: Span列表
        """
        query = db.query(Span).filter(Span.trace_id == trace_id)

        if not include_details:
            # 只查询基础字段，提高性能
            query = query.with_entities(
                Span.id,
                Span.trace_id,
                Span.span_id,
                Span.parent_span_id,
                Span.name,
                Span.class_name,
                Span.module_name,
                Span.start_time,
                Span.end_time,
                Span.duration_ms,
                Span.exception,
                Span.created_at
            )

        spans = query.order_by(Span.start_time.asc()).all()
        return spans

    @staticmethod
    def get_span_by_id(db: Session, span_id: int) -> Optional[Span]:
        """根据Span ID查询详情

        :param db: 数据库会话
        :param span_id: Span ID
        :return: Span 对象，不存在返回 None
        """
        return db.query(Span).filter(Span.id == span_id).first()

    @staticmethod
    def get_child_spans(db: Session, trace_id: str, parent_span_id: str) -> List[Span]:
        """查询父Span的所有子Span

        :param db: 数据库会话
        :param trace_id: 链路唯一标识
        :param parent_span_id: 父Span ID
        :return: 子Span列表
        """
        return db.query(Span).filter(
            Span.trace_id == trace_id,
            Span.parent_span_id == parent_span_id
        ).order_by(Span.start_time.asc()).all()

    @staticmethod
    def get_span_count_by_trace_id(db: Session, trace_id: str) -> int:
        """查询Trace关联的Span数量

        :param db: 数据库会话
        :param trace_id: 链路唯一标识
        :return: Span数量
        """
        return db.query(func.count(Span.id)).filter(Span.trace_id == trace_id).scalar() or 0

    @staticmethod
    def get_total_span_duration_by_trace_id(db: Session, trace_id: str) -> float:
        """查询Trace所有Span的总耗时

        :param db: 数据库会话
        :param trace_id: 链路唯一标识
        :return: 总耗时(毫秒)
        """
        return db.query(func.sum(Span.duration_ms)).filter(Span.trace_id == trace_id).scalar() or 0.0

    @staticmethod
    def get_statistics(
        db: Session,
        period: str = "7d",
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """查询Trace统计数据

        :param db: 数据库会话
        :param period: 统计周期：1d(最近1天)、7d(最近7天)、30d(最近30天)、all(全部)
        :param user_id: 按用户ID筛选（可选）
        :param start_time: 自定义开始时间（可选，优先于period）
        :param end_time: 自定义结束时间（可选，优先于period）
        :return: 统计数据字典
        """
        # 计算时间范围
        if not start_time or not end_time:
            end_time_calc = datetime.now()
            if period == "1d":
                start_time_calc = end_time_calc - timedelta(days=1)
                period_desc = "最近1天"
            elif period == "7d":
                start_time_calc = end_time_calc - timedelta(days=7)
                period_desc = "最近7天"
            elif period == "30d":
                start_time_calc = end_time_calc - timedelta(days=30)
                period_desc = "最近30天"
            elif period == "all":
                start_time_calc = None
                period_desc = "全部"
            else:
                # 默认7天
                start_time_calc = end_time_calc - timedelta(days=7)
                period_desc = "最近7天"
        else:
            start_time_calc = start_time
            end_time_calc = end_time
            period_desc = f"{start_time.strftime('%Y-%m-%d')} 至 {end_time.strftime('%Y-%m-%d')}"

        # 基础查询
        query = db.query(Trace)

        # 条件筛选
        filters = []
        if start_time_calc is not None:
            filters.append(Trace.created_at >= start_time_calc)
        if end_time_calc is not None:
            filters.append(Trace.created_at <= end_time_calc)
        if user_id is not None:
            filters.append(Trace.user_id == user_id)

        if filters:
            query = query.filter(and_(*filters))

        # 基础统计
        total_count = query.count()
        if total_count == 0:
            return {
                "total_count": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "p50_duration": 0.0,
                "p95_duration": 0.0,
                "p99_duration": 0.0,
                "total_span_count": 0,
                "avg_span_per_trace": 0.0,
                "period": period_desc
            }

        # 成功/失败统计
        success_count = query.filter(Trace.status_code < 400).count()
        error_count = total_count - success_count
        success_rate = success_count / total_count if total_count > 0 else 0.0

        # 耗时统计
        avg_duration = db.query(func.avg(Trace.duration_ms)).filter(*filters).scalar() or 0.0

        # 百分位统计（MySQL不支持percentile_cont，在应用层计算）
        durations = db.query(Trace.duration_ms).filter(*filters).order_by(Trace.duration_ms).all()
        duration_list = [float(d[0]) for d in durations if d[0] is not None]


        if duration_list:
            n = len(duration_list)

            # 计算百分位数的辅助函数
            def percentile(data, p):
                k = (len(data) - 1) * p
                f = int(k)
                c = f + 1 if f + 1 < len(data) else f
                d0 = data[f] * (c - k)
                d1 = data[c] * (k - f)
                return d0 + d1

            p50_duration = percentile(duration_list, 0.5)
            p95_duration = percentile(duration_list, 0.95)
            p99_duration = percentile(duration_list, 0.99)
        else:
            p50_duration = 0.0
            p95_duration = 0.0
            p99_duration = 0.0

        # Span统计
        total_span_count = db.query(func.count(Span.id)).filter(
            Span.trace_id.in_(query.with_entities(Trace.trace_id))
        ).scalar() or 0
        avg_span_per_trace = total_span_count / total_count if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": round(success_rate, 4),
            "avg_duration": round(float(avg_duration), 2),
            "p50_duration": round(float(p50_duration), 2),
            "p95_duration": round(float(p95_duration), 2),
            "p99_duration": round(float(p99_duration), 2),
            "total_span_count": total_span_count,
            "avg_span_per_trace": round(avg_span_per_trace, 2),
            "period": period_desc
        }


# 全局DAO实例
trace_management_dao = TraceManagementDAO()
