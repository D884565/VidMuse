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
3. 自动推送配置示例（已废弃，建议使用hooks）：
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
4. 新的钩子使用方式：
    from backend.trace import trace, TraceHooks
    def on_start(span):
        print(f"函数开始执行: {span.name}")
    @trace(hooks=TraceHooks(on_start=on_start))
    def my_function():
        pass
"""
from .decorator import trace, PushConfig
from .middleware import TraceMiddleware
from .context import get_trace_id, get_current_span, Span, get_user_id, set_user_id
from .config import trace_config
from .hooks import TraceHooks
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
    "TraceHooks",  # 新增导出
]
__version__ = "2.0.0"  # 版本升级，表示架构变更
