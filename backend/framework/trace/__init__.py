"""
全链路追踪系统

使用方式：
1. 在FastAPI应用中添加中间件：
    from fastapi import FastAPI
    from backend.trace import TraceMiddleware

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

2. 在需要追踪的函数上添加装饰器：
    from backend.trace import trace

    @trace
    def my_function():
        pass
"""

from .decorator import trace
from .middleware import TraceMiddleware
from .context import get_trace_id, get_current_span, Span, get_user_id, set_user_id
from .config import trace_config


__all__ = [
    "trace",
    "TraceMiddleware",
    "get_trace_id",
    "get_user_id",
    "set_user_id",
    "get_current_span",
    "Span",
    "trace_config",
]

__version__ = "1.0.0"
