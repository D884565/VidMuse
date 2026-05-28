"""请求追踪中间件 — 管理链路上下文生命周期"""
import uuid
import time
import logging
import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .trace_context import request_id_var, span_stack_var, Span

logger = logging.getLogger("trace")


async def _save_trace_log(
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    span_tree: dict | None,
) -> None:
    """异步写入链路记录到 trace_log 表"""
    try:
        from backend.store.database.async_database import SessionLocal
        from backend.framework.log.trace_model import TraceLog

        async with SessionLocal() as session:
            trace = TraceLog(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
                span_tree=span_tree,
            )
            session.add(trace)
            await session.commit()
    except Exception:
        logger.error("链路数据写入失败", exc_info=True)


class TraceMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求自动设置链路上下文，记录生命周期日志"""

    async def dispatch(self, request: Request, call_next):
        # 1. 生成或复用 request_id
        req_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:8])
        token_req = request_id_var.set(req_id)
        token_stack = span_stack_var.set([])

        root_span = Span(name=f"{request.method} {request.url.path}")

        try:
            logger.info(">>> 请求开始")

            response = await call_next(request)
            root_span.end = time.time()

            logger.info(
                f"<<< 请求完成 status={response.status_code} "
                f"cost={root_span.duration_ms:.1f}ms"
            )
            response.headers["X-Request-Id"] = req_id

            # 2. 异步写入链路数据（不阻塞响应）
            asyncio.create_task(_save_trace_log(
                request_id=req_id,
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=root_span.duration_ms,
                span_tree=root_span.to_dict(),
            ))
            return response

        except Exception as e:
            root_span.end = time.time()
            logger.error(
                f"!!! 请求异常 cost={root_span.duration_ms:.1f}ms",
                exc_info=True,
            )

            # 3. 异常时也写入链路数据
            asyncio.create_task(_save_trace_log(
                request_id=req_id,
                method=request.method,
                path=str(request.url.path),
                status_code=500,
                duration_ms=root_span.duration_ms,
                span_tree=root_span.to_dict(),
            ))
            raise
        finally:
            request_id_var.reset(token_req)
            span_stack_var.reset(token_stack)
