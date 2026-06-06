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

3. 自动推送配置示例：
    from backend.trace import trace, PushConfig

    def get_user_id(*args, **kwargs):
        return kwargs.get("user_id")

    def start_msg(func, args, kwargs):
        return ("agent_progress", "开始处理", {"progress": 0})

    @trace(
        push_config=PushConfig(
            enable_push=True,
            user_id_getter=get_user_id,
            push_on_start=True,
            start_message_generator=start_msg
        )
    )
    async def agent_execute(user_id: int):
        pass
"""

from .decorator import trace, PushConfig
from .middleware import TraceMiddleware
from .context import get_trace_id, get_current_span, Span, get_user_id, set_user_id
from .config import trace_config


__all__ = [
    "trace",
    "PushConfig",
    "TraceMiddleware",
    "get_trace_id",
    "get_user_id",
    "set_user_id",
    "get_current_span",
    "Span",
    "trace_config",
]

__version__ = "1.1.0"
