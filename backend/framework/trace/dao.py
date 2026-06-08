"""链路追踪数据访问层
职责：封装所有对traces和spans表的数据库操作，提供批量写入功能
"""
import asyncio
import json
import logging
import threading
from typing import Any, List, Optional

from backend.store.database.async_database import SessionLocal
from .models import Trace, Span as SpanModel
from .context import Span, get_trace_id
from .config import trace_config

logger = logging.getLogger("trace.dao")

# 批量队列和线程锁（支持跨线程安全访问）
_batch_queue: List[Span] = []
_batch_lock = threading.Lock()


def _serialize_value(value: Any, max_length: int) -> Any:
    """
    序列化任意值为JSON可序列化格式
    处理不可序列化对象、循环引用、超长字符串截断
    """
    if value is None:
        return None

    try:
        # 先尝试直接JSON序列化
        json.dumps(value)
        serialized = value
    except (TypeError, ValueError, OverflowError):
        # 不可序列化则转为字符串
        try:
            serialized = repr(value)
        except:
            serialized = "<unserializable object>"

    # 处理字符串长度截断
    if isinstance(serialized, str) and len(serialized) > max_length:
        truncated_length = max_length - 15  # 留位置给截断提示
        serialized = serialized[:truncated_length] + f"... [truncated, total {len(serialized)} chars]"

    return serialized


def _convert_span_to_model(span: Span, trace_id: str) -> SpanModel:
    """
    将上下文Span对象转换为数据库SpanModel
    根据配置决定是否记录参数、返回值和堆栈信息
    """
    # 序列化参数
    serialized_args = None
    serialized_kwargs = None
    if trace_config.TRACE_RECORD_ARGS:
        if span.args:
            serialized_args = [_serialize_value(arg, trace_config.TRACE_MAX_ARG_LENGTH) for arg in span.args]
        if span.kwargs:
            serialized_kwargs = {k: _serialize_value(v, trace_config.TRACE_MAX_ARG_LENGTH) for k, v in span.kwargs.items()}

    # 序列化返回值
    return_value = None
    if trace_config.TRACE_RECORD_RETURN and span.return_value is not None:
        return_value = _serialize_value(span.return_value, trace_config.TRACE_MAX_RETURN_LENGTH)

    # 处理异常信息
    exception = None
    stack_trace = None
    if span.exception is not None:
        exception = str(span.exception)
        if trace_config.TRACE_RECORD_STACK and span.stack_trace:
            stack_trace = span.stack_trace

    return SpanModel(
        trace_id=trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        name=span.name,
        class_name=span.class_name,
        module_name=span.module_name,
        start_time=span.start_time,
        end_time=span.end_time,
        duration_ms=span.duration_ms,
        args=serialized_args,
        kwargs=serialized_kwargs,
        return_value=return_value,
        exception=exception,
        stack_trace=stack_trace,
        meta_data=span.meta_data
    )


async def save_trace_data(
    trace_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: Optional[str] = None,
    user_id: Optional[int] = None,
    user_agent: Optional[str] = None,
    request_headers: Optional[dict] = None,
    response_headers: Optional[dict] = None,
    spans: Optional[List[Span]] = None
) -> None:
    """
    异步保存Trace记录和关联的所有Spans到数据库
    所有异常捕获并记录日志，不抛出异常避免影响业务流程
    """
    if not trace_config.TRACE_ENABLED:
        return

    async with SessionLocal() as session:
        try:
            # 创建Trace记录
            trace = Trace(
                trace_id=trace_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
                client_ip=client_ip,
                user_id=user_id,
                user_agent=user_agent,
                request_headers=request_headers,
                response_headers=response_headers
            )
            session.add(trace)

            # 处理Spans
            if spans:
                span_models = [_convert_span_to_model(span, trace_id) for span in spans]
                session.add_all(span_models)

            await session.commit()
            logger.debug(f"Successfully saved trace {trace_id} with {len(spans or [])} spans")

        except Exception as e:
            logger.error(f"Failed to save trace {trace_id}: {str(e)}", exc_info=True)
            try:
                await session.rollback()
            except:
                pass


async def batch_save_spans(spans: List[Span], trace_id: Optional[str] = None) -> None:
    """
    批量保存多个Span到数据库
    如果trace_id为None则从当前上下文获取
    """
    if not trace_config.TRACE_ENABLED or not spans:
        return

    current_trace_id = trace_id or get_trace_id()
    # 如果没有全局trace_id，尝试从第一个span获取（适用于独立运行的span）
    if not current_trace_id and spans:
        current_trace_id = spans[0].trace_id
    if not current_trace_id:
        logger.warning("No trace_id provided and no trace context found, skipping span save")
        return

    async with SessionLocal() as session:
        try:
            span_models = [_convert_span_to_model(span, current_trace_id) for span in spans]
            session.add_all(span_models)
            await session.commit()
            logger.debug(f"Successfully batch saved {len(span_models)} spans for trace {current_trace_id}")

        except Exception as e:
            logger.error(f"Failed to batch save spans: {str(e)}", exc_info=True)
            try:
                await session.rollback()
            except:
                pass


async def add_to_batch(span: Span, trace_id: Optional[str] = None) -> None:
    """
    将Span添加到批量队列，达到批量大小阈值时自动触发写入
    """
    if not trace_config.TRACE_ENABLED:
        return

    # 如果提供了trace_id，覆盖span中的trace_id
    if trace_id:
        span.trace_id = trace_id

    flush_queue = None
    with _batch_lock:
        _batch_queue.append(span)

        # 达到批量大小则触发写入
        if len(_batch_queue) >= trace_config.TRACE_BATCH_SIZE:
            # 拷贝队列数据，避免长时间持有锁
            flush_queue = _batch_queue.copy()
            _batch_queue.clear()

    # 释放锁后再执行IO操作
    if flush_queue is not None:
        await _flush_spans(flush_queue)


async def flush_batch() -> None:
    """
    手动将队列中的所有Span写入数据库
    """
    if not trace_config.TRACE_ENABLED:
        return

    with _batch_lock:
        if not _batch_queue:
            return
        # 拷贝队列数据
        queue_copy = _batch_queue.copy()
        _batch_queue.clear()

    # 释放锁后执行IO操作
    await _flush_spans(queue_copy)


async def _flush_spans(spans: List[Span]) -> None:
    """
    刷新指定的spans列表到数据库
    """
    if not spans:
        return

    try:
        # 按trace_id分组spans
        spans_by_trace = {}
        import uuid
        for span in spans:
            current_trace_id = span.trace_id
            # 没有trace_id的span自动生成一个（保持和中间件一致的8位长度）
            if not current_trace_id:
                current_trace_id = uuid.uuid4().hex[:8]
                span.trace_id = current_trace_id
            if current_trace_id not in spans_by_trace:
                spans_by_trace[current_trace_id] = []
            spans_by_trace[current_trace_id].append(span)

        # 批量保存每个trace的spans
        for trace_id, trace_spans in spans_by_trace.items():
            await batch_save_spans(trace_spans, trace_id)

        logger.debug(f"Flushed batch of {len(spans)} spans")

    except Exception as e:
        logger.error(f"Failed to flush span batch: {str(e)}", exc_info=True)


async def _flush_batch_internal() -> None:
    """
    内部批量写入实现（保留用于兼容）
    """
    global _batch_queue

    if not _batch_queue:
        return

    try:
        # 拷贝队列数据，避免长时间占用
        spans_to_flush = _batch_queue.copy()
        _batch_queue.clear()

        # 按trace_id分组spans
        spans_by_trace = {}
        import uuid
        for span in spans_to_flush:
            current_trace_id = span.trace_id
            # 没有trace_id的span自动生成一个（保持和中间件一致的8位长度）
            if not current_trace_id:
                current_trace_id = uuid.uuid4().hex[:8]
                span.trace_id = current_trace_id
            if current_trace_id not in spans_by_trace:
                spans_by_trace[current_trace_id] = []
            spans_by_trace[current_trace_id].append(span)

        # 批量保存每个trace的spans
        for trace_id, spans in spans_by_trace.items():
            await batch_save_spans(spans, trace_id)

        logger.debug(f"Flushed batch of {len(spans_to_flush)} spans")

    except Exception as e:
        logger.error(f"Failed to flush span batch: {str(e)}", exc_info=True)
