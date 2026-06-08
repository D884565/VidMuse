"""Trace装饰器实现"""
import inspect
import functools
import asyncio
from typing import Any, Callable, Optional, TypeVar, TYPE_CHECKING
from .context import start_span, end_span, get_trace_id
from .dao import add_to_batch
from .hooks import TraceHooks
from .compat import PushConfig, PushConfigType, _sync_push
__all__ = ["trace", "PushConfig", "_sync_push"]
T = TypeVar("T", bound=Callable[..., Any])
def _get_create_push_hooks():
    """
    动态获取push_config转hooks的函数
    避免trace框架依赖push服务
    """
    try:
        from backend.v1.app.push.trace_extension import create_push_hooks
        return create_push_hooks
    except ImportError:
        # 如果push服务不可用，返回空函数
        return lambda push_config, *args, **kwargs: TraceHooks()
def trace(
    *args: Any,
    name: Optional[str] = None,
    meta_data: Optional[dict] = None,
    push_config: PushConfigType = None,
    hooks: Optional[TraceHooks] = None
) -> Callable[[T], T]:
    """
    装饰器，用于标记需要追踪的函数
    Args:
        name: 自定义span名称，默认使用函数名
        meta_data: 扩展元数据
        push_config: （已废弃）推送配置，建议使用hooks参数替代
        hooks: 生命周期钩子，用于在函数执行的不同阶段注入自定义行为
    Examples:
        @trace
        def my_function():
            pass
        @trace(name="自定义名称", meta_data={"type": "database"})
        def query_data():
            pass
        # 使用钩子的新方式
        from backend.framework.trace import TraceHooks
        def on_start(span):
            print(f"函数开始执行: {span.name}")
        @trace(hooks=TraceHooks(on_start=on_start))
        def my_function():
            pass
        # 兼容原有推送配置
        from backend.framework.trace import PushConfig
        def get_user_id(*args, **kwargs):
            return kwargs.get("user_id")
        def start_msg(*args, **kwargs):
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
    def decorator(func: T) -> T:
        # 获取函数信息
        func_name = name or func.__name__
        module_name = func.__module__
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        is_class_method = False
        # 检查是否是类方法或实例方法
        if params and params[0] in ("self", "cls"):
            is_class_method = True
        # 处理hooks：合并push_config转换的hooks和传入的hooks
        final_hooks = TraceHooks()
        if push_config:
            create_push_hooks = _get_create_push_hooks()
            push_hooks = create_push_hooks(push_config, func)
            final_hooks = TraceHooks.merge(final_hooks, push_hooks)
        if hooks:
            final_hooks = TraceHooks.merge(final_hooks, hooks)
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 确定类名和绑定方法
            class_name = None
            if is_class_method and args:
                if params[0] == "self":
                    class_name = args[0].__class__.__name__
                else:  # cls
                    class_name = args[0].__name__
            # 启动span
            span = start_span(
                name=func_name,
                module_name=module_name,
                class_name=class_name,
                meta_data=meta_data,
            )
            # 记录参数
            span.args = args
            span.kwargs = kwargs
            # 执行on_start钩子
            if final_hooks.on_start:
                try:
                    final_hooks.on_start(span)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to execute on_start hook: {e}", exc_info=True)
            try:
                # 执行函数
                result = func(*args, **kwargs)
                span.return_value = result
                # 执行on_end钩子
                if final_hooks.on_end:
                    try:
                        final_hooks.on_end(span)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to execute on_end hook: {e}", exc_info=True)
                return result
            except Exception as e:
                span.set_exception(e)
                # 执行on_error钩子
                if final_hooks.on_error:
                    try:
                        final_hooks.on_error(span, e)
                    except Exception as hook_e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to execute on_error hook: {hook_e}", exc_info=True)
                raise
            finally:
                # 结束span
                end_span(span)
                # 只有当没有trace上下文时（说明在独立线程中运行），才添加到批量队列
                # 有上下文的span会在中间件中统一保存
                if not get_trace_id():
                    # 如果span没有trace_id，自动生成一个（保持和中间件一致的8位长度）
                    if not span.trace_id:
                        import uuid
                        span.trace_id = uuid.uuid4().hex[:8]
                    # 异步添加到批量队列
                    asyncio.create_task(add_to_batch(span))
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 确定类名和绑定方法
            class_name = None
            if is_class_method and args:
                if params[0] == "self":
                    class_name = args[0].__class__.__name__
                else:  # cls
                    class_name = args[0].__name__
            # 启动span
            span = start_span(
                name=func_name,
                module_name=module_name,
                class_name=class_name,
                meta_data=meta_data,
            )
            # 记录参数
            span.args = args
            span.kwargs = kwargs
            # 执行on_start钩子
            if final_hooks.on_start:
                try:
                    if asyncio.iscoroutinefunction(final_hooks.on_start):
                        await final_hooks.on_start(span)
                    else:
                        final_hooks.on_start(span)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to execute on_start hook: {e}", exc_info=True)
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                span.return_value = result
                # 执行on_end钩子
                if final_hooks.on_end:
                    try:
                        if asyncio.iscoroutinefunction(final_hooks.on_end):
                            await final_hooks.on_end(span)
                        else:
                            final_hooks.on_end(span)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to execute on_end hook: {e}", exc_info=True)
                return result
            except Exception as e:
                span.set_exception(e)
                # 执行on_error钩子
                if final_hooks.on_error:
                    try:
                        if asyncio.iscoroutinefunction(final_hooks.on_error):
                            await final_hooks.on_error(span, e)
                        else:
                            final_hooks.on_error(span, e)
                    except Exception as hook_e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to execute on_error hook: {hook_e}", exc_info=True)
                raise
            finally:
                # 结束span（异步函数的span会在中间件中统一保存，不需要单独添加到批量队列）
                end_span(span)
        # 判断是同步还是异步函数
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    # 处理无参数的装饰器调用情况：@trace
    if len(args) == 1 and callable(args[0]):
        return decorator(args[0])
    # 处理带参数的装饰器调用情况：@trace(name="xxx")
    return decorator
