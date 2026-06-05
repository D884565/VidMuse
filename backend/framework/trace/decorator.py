"""Trace装饰器实现"""
import inspect
import functools
import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar, Tuple, TYPE_CHECKING

# 类型检查时导入，运行时延迟导入
if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from .context import start_span, end_span, get_trace_id
from .dao import add_to_batch

# 延迟导入，避免循环依赖
_get_db = None
_push_service = None

def _get_db_session():
    global _get_db
    if _get_db is None:
        from backend.framework.db.session import get_db
        _get_db = get_db
    return next(_get_db())

def _get_push_service():
    global _push_service
    if _push_service is None:
        from backend.v1.app.push import push_service
        _push_service = push_service
    return _push_service


T = TypeVar("T", bound=Callable[..., Any])

# 后台事件循环用于同步函数中的异步操作
_background_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


@dataclass
class PushConfig:
    """
    Trace推送配置类
    用于配置@trace注解的自动推送行为
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


# 推送配置类型别名
PushConfigType = Optional[PushConfig]


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


async def _do_push(
    push_config: PushConfig,
    user_id: int,
    message_generator: Callable,
    *generator_args: Any,
    **generator_kwargs: Any
) -> None:
    """
    内部推送执行函数
    :param push_config: 推送配置
    :param user_id: 目标用户ID
    :param message_generator: 消息生成回调
    :param generator_args: 传递给消息生成器的参数
    :param generator_kwargs: 传递给消息生成器的关键字参数
    """
    try:
        # 生成消息
        msg_data = message_generator(*generator_args, **generator_kwargs)
        if len(msg_data) == 3:
            message_type, title, content = msg_data
            level = "info"
        else:
            message_type, title, content, level = msg_data

        # 获取数据库会话（延迟导入）
        db = _get_db_session()
        try:
            # 获取推送服务（延迟导入）
            push_service = _get_push_service()

            # 推送消息
            await push_service.push_message(
                db=db,
                user_id=user_id,
                message_type=message_type,
                title=title,
                content=content,
                level=level,
                persist=push_config.persist_messages
            )
        finally:
            db.close()

    except Exception as e:
        # 推送过程中的异常不影响主业务流程，只记录日志
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to push message in trace decorator: {e}", exc_info=True)


def _sync_push(
    push_config: PushConfig,
    user_id: int,
    message_generator: Callable,
    *generator_args: Any,
    **generator_kwargs: Any
) -> None:
    """同步函数中调用推送，在后台执行"""
    _run_async(_do_push(
        push_config, user_id, message_generator,
        *generator_args, **generator_kwargs
    ))


def trace(
    *args: Any,
    name: Optional[str] = None,
    meta_data: Optional[dict] = None,
    push_config: PushConfigType = None
) -> Callable[[T], T]:
    """
    装饰器，用于标记需要追踪的函数

    Args:
        name: 自定义span名称，默认使用函数名
        meta_data: 扩展元数据
        push_config: 推送配置，启用后自动在函数执行的不同阶段推送消息

    Examples:
        @trace
        def my_function():
            pass

        @trace(name="自定义名称", meta_data={"type": "database"})
        def query_data():
            pass

        # 带推送配置的使用示例
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

            # 推送：函数开始
            user_id = None
            if push_config and push_config.enable_push and push_config.push_on_start:
                try:
                    if push_config.user_id_getter:
                        user_id = push_config.user_id_getter(*args, **kwargs)
                        if push_config.start_message_generator:
                            _sync_push(
                                push_config, user_id,
                                push_config.start_message_generator,
                                func, args, kwargs
                            )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to push start message: {e}")

            try:
                # 执行函数
                result = func(*args, **kwargs)
                span.return_value = result

                # 推送：函数成功结束
                if push_config and push_config.enable_push and push_config.push_on_end and user_id is not None:
                    try:
                        if push_config.end_message_generator:
                            _sync_push(
                                push_config, user_id,
                                push_config.end_message_generator,
                                func, result
                            )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to push end message: {e}")

                return result

            except Exception as e:
                span.set_exception(e)

                # 推送：函数异常
                if push_config and push_config.enable_push and push_config.push_on_error and user_id is not None:
                    try:
                        if push_config.error_message_generator:
                            _sync_push(
                                push_config, user_id,
                                push_config.error_message_generator,
                                func, e
                            )
                    except Exception as push_e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to push error message: {push_e}")

                raise

            finally:
                # 结束span
                end_span(span)
                # 只有当没有trace上下文时（说明在独立线程中运行），才添加到批量队列
                # 有上下文的span会在中间件中统一保存
                if not get_trace_id():
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

            # 推送：函数开始
            user_id = None
            if push_config and push_config.enable_push and push_config.push_on_start:
                try:
                    if push_config.user_id_getter:
                        user_id = push_config.user_id_getter(*args, **kwargs)
                        if push_config.start_message_generator:
                            # 异步推送，不阻塞主流程
                            asyncio.create_task(_do_push(
                                push_config, user_id,
                                push_config.start_message_generator,
                                func, args, kwargs
                            ))
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to push start message: {e}")

            try:
                # 执行函数
                result = await func(*args, **kwargs)
                span.return_value = result

                # 推送：函数成功结束
                if push_config and push_config.enable_push and push_config.push_on_end and user_id is not None:
                    try:
                        if push_config.end_message_generator:
                            asyncio.create_task(_do_push(
                                push_config, user_id,
                                push_config.end_message_generator,
                                func, result
                            ))
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to push end message: {e}")

                return result

            except Exception as e:
                span.set_exception(e)

                # 推送：函数异常
                if push_config and push_config.enable_push and push_config.push_on_error and user_id is not None:
                    try:
                        if push_config.error_message_generator:
                            asyncio.create_task(_do_push(
                                push_config, user_id,
                                push_config.error_message_generator,
                                func, e
                            ))
                    except Exception as push_e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to push error message: {push_e}")

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
