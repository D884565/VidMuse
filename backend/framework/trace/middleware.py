"""Trace middleware for FastAPI"""
import uuid
import time
import asyncio
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import trace_id_var, span_stack_var, get_all_spans, clear_context, start_span, end_span, set_user_id, get_user_id
from .dao import save_trace_data, flush_batch
from .config import trace_config
from backend.framework.web.auth import parse_token_from_header
from backend.framework.exceptions.exceptions import BusinessException


logger = logging.getLogger("trace.middleware")


class TraceMiddleware(BaseHTTPMiddleware):
    """
    链路追踪中间件，为每个HTTP请求自动创建链路上下文

    Usage:
        from fastapi import FastAPI
        from backend.trace import TraceMiddleware

        app = FastAPI()
        app.add_middleware(TraceMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        if not trace_config.TRACE_ENABLED:
            return await call_next(request)

        # 1. 生成或复用trace_id
        trace_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:8])

        # 设置上下文
        token_trace = trace_id_var.set(trace_id)
        token_stack = span_stack_var.set([])

        # 尝试获取并设置用户ID（公共接口可能没有token，忽略异常）
        user_id = None
        try:
            user_id = parse_token_from_header(request.headers.get("Authorization"))
        except BusinessException as exc:
            logger.info("trace auth parse skipped: code=%s, path=%s", exc.code, request.url.path)
        if user_id:
            set_user_id(user_id)

        # 创建根span，代表整个请求
        root_span = start_span(
            name=f"{request.method} {request.url.path}",
            module_name="http.request",
        )

        start_time = time.time()
        response: Optional[Response] = None

        try:
            logger.info(f"Request started: {request.method} {request.url.path}, trace_id={trace_id}")

            # 执行请求
            response = await call_next(request)

            # 请求成功
            root_span.return_value = response.status_code
            response.headers["X-Request-Id"] = trace_id

            logger.info(
                f"Request completed: {request.method} {request.url.path}, "
                f"status={response.status_code}, cost={root_span.duration_ms:.1f}ms, "
                f"trace_id={trace_id}"
            )

            return response

        except Exception as e:
            # 请求异常
            root_span.set_exception(e)
            logger.error(
                f"Request failed: {request.method} {request.url.path}, "
                f"cost={root_span.duration_ms:.1f}ms, trace_id={trace_id}",
                exc_info=True
            )
            raise

        finally:
            # 获取所有spans（必须在end_span之前获取，否则根span会被弹出栈）
            spans = get_all_spans()

            # 结束根span
            end_span(root_span)
            duration_ms = root_span.duration_ms
            status_code = response.status_code if response else 500

            # 获取客户端IP
            client_ip = self._get_client_ip(request)

            # 获取请求头和响应头
            request_headers = dict(request.headers)
            response_headers = dict(response.headers) if response else {}

            # 获取用户ID
            user_id = get_user_id()

            # 无论是否有response都保存数据（包括异常情况）
            asyncio.create_task(self._save_trace_async(
                trace_id=trace_id,
                user_id=user_id,
                method=request.method,
                path=str(request.url.path),
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=request.headers.get("user-agent"),
                request_headers=request_headers,
                response_headers=response_headers,
                spans=spans,
            ))

            # 清理上下文
            trace_id_var.reset(token_trace)
            span_stack_var.reset(token_stack)
            clear_context()

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()
        if "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"]
        return request.client.host if request.client else ""

    async def _save_trace_async(
        self,
        trace_id: str,
        user_id: Optional[int],
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_headers: Optional[dict] = None,
        response_headers: Optional[dict] = None,
        spans: Optional[list] = None,
    ) -> None:
        """异步保存链路数据"""
        try:
            # 根据配置决定是否刷新批量队列中的span（确保同步函数数据及时落库）
            if trace_config.TRACE_FLUSH_ON_REQUEST_END:
                await flush_batch()

            # 保存完整链路数据
            await save_trace_data(
                trace_id=trace_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=user_agent,
                request_headers=request_headers,
                response_headers=response_headers,
                spans=spans,
            )

        except Exception as e:
            logger.error(f"Failed to save trace data in background: {str(e)}", exc_info=True)
