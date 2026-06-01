"""Trace装饰器实现"""
import inspect
import functools
import asyncio
import threading
from typing import Any, Callable, Optional, TypeVar
from .context import start_span, end_span
from .dao import add_to_batch


T = TypeVar("T", bound=Callable[..., Any])

# 后台事件循环用于同步函数中的异步操作
_background_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _get_background_loop() -> asyncio.AbstractEventLoop:
    """获取或创建后台事件循环"""
    global _background_loop, _loop_thread

    if _background_loop is None:
        _background_loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_background_loop.run_forever, daemon=True)
        _loop_thread.start()

    return _background_loop


def _run_async(coro):
    """在后台事件循环中运行协程"""
    loop = _get_background_loop()
    asyncio.run_coroutine_threadsafe(coro, loop)


def trace(*args: Any, name: Optional[str] = None, meta_data: Optional[dict] = None) -> Callable[[T], T]:
    """
    装饰器，用于标记需要追踪的函数

    Args:
        name: 自定义span名称，默认使用函数名
        meta_data: 扩展元数据

    Examples:
        @trace
        def my_function():
            pass

        @trace(name="自定义名称", meta_data={"type": "database"})
        def query_data():
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

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 确定类名
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

            try:
                # 执行函数
                result = func(*args, **kwargs)
                span.return_value = result
                return result

            except Exception as e:
                span.set_exception(e)
                raise

            finally:
                # 结束span并保存
                end_span(span)
                # 在后台事件循环中异步添加到批量队列
                _run_async(add_to_batch(span))

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 确定类名
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

            try:
                # 执行函数
                result = await func(*args, **kwargs)
                span.return_value = result
                return result

            except Exception as e:
                span.set_exception(e)
                raise

            finally:
                # 结束span并保存
                end_span(span)
                await add_to_batch(span)

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
