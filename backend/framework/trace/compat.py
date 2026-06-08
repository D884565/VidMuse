"""
向后兼容层
保持对原有PushConfig API的兼容，平滑迁移到新的钩子机制
"""
import asyncio
import threading
from typing import Callable, Optional, Tuple, Any, TypeVar
from dataclasses import dataclass
from .hooks import TraceHooks
from .context import Span
T = TypeVar("T", bound=Callable[..., Any])
# 推送配置类型别名
PushConfigType = Optional["PushConfig"]
@dataclass
class PushConfig:
    """
    兼容原有PushConfig接口
    已废弃，请使用TraceHooks替代
    """
    # 基础开关
    enable_push: bool = False  # 是否启用自动推送
    # 用户ID获取
    user_id_getter: Optional[Callable[..., int]] = None  # 从函数参数中获取用户ID的回调
    # 推送时机配置
    push_on_start: bool = False  # 函数执行开始时推送
    push_on_end: bool = False  # 函数执行成功结束时推送
    push_on_error: bool = True  # 函数执行异常时推送
    # 消息生成回调
    # 回调返回格式: (message_type: str, title: str, content: Any, level: str = "info")
    start_message_generator: Optional[Callable[..., Tuple[str, str, Any] | Tuple[str, str, Any, str]]] = None
    end_message_generator: Optional[Callable[..., Tuple[str, str, Any] | Tuple[str, str, Any, str]]] = None
    error_message_generator: Optional[Callable[..., Tuple[str, str, Any] | Tuple[str, str, Any, str]]] = None
    # 持久化配置
    persist_messages: bool = True  # 是否将消息持久化到数据库
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
def _sync_push(
    push_config: PushConfig,
    user_id: int,
    message_generator: Callable,
    *generator_args: Any,
    **generator_kwargs: Any
) -> None:
    """
    兼容原有_sync_push API
    已废弃，请直接调用push_service.push_message
    """
    try:
        from backend.v1.app.push.trace_extension import do_push
        _run_async(do_push(
            push_config, user_id, message_generator,
            *generator_args, **generator_kwargs
        ))
    except ImportError:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Push service not available, _sync_push is no-op")
def push_config_to_hooks(push_config: PushConfig) -> TraceHooks:
    """
    将旧的PushConfig转换为新的TraceHooks格式
    内部使用，业务代码不应该直接调用
    """
    if not push_config or not push_config.enable_push:
        return TraceHooks()
    # 这里只是占位，实际的转换逻辑会在push服务的扩展模块中实现
    # 因为转换需要依赖push_service，而trace框架不能依赖push服务
    # 这个函数会在装饰器的兼容逻辑中被动态替换
    return TraceHooks()
__all__ = ["PushConfig", "PushConfigType", "_sync_push", "push_config_to_hooks"]
