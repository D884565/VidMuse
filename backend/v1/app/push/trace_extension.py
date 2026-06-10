"""
Trace推送扩展
实现trace钩子与push服务的集成，作为trace框架的扩展插件
"""
import asyncio
from typing import Any, Callable, Tuple, Optional
from backend.framework.trace import Span
from backend.framework.trace.compat import PushConfig
from backend.framework.trace.hooks import TraceHooks
from .service import push_service
from backend.store.database.async_database import SessionLocal

# 保存所有后台推送任务的引用，防止被GC回收
_background_push_tasks: set[asyncio.Task] = set()
async def do_push(
    push_config: PushConfig,
    user_id: int,
    message_generator: Callable,
    *generator_args: Any,
    **generator_kwargs: Any
) -> None:
    """
    执行推送操作
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
        # 获取数据库会话
        async with SessionLocal() as db:
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
    except Exception as e:
        # 推送过程中的异常不影响主业务流程，只记录日志
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to push message in trace extension: {e}", exc_info=True)
def create_push_hooks(push_config: PushConfig, func: Callable) -> TraceHooks:
    """
    根据PushConfig创建对应的trace钩子
    :param push_config: 推送配置
    :param func: 被装饰的函数对象
    :return: TraceHooks对象
    """
    if not push_config or not push_config.enable_push:
        return TraceHooks()
    def on_start(span: Span):
        """函数开始时的钩子"""
        if not push_config.push_on_start:
            return
        try:
            if push_config.user_id_getter and push_config.start_message_generator:
                user_id = push_config.user_id_getter(*span.args, **span.kwargs)
                if user_id:
                    # 绑定方法处理
                    bound_func = func
                    if hasattr(func, '__get__') and span.args:
                        bound_func = func.__get__(span.args[0], span.args[0].__class__)
                    # 异步推送
                    task = asyncio.create_task(do_push(
                        push_config, user_id,
                        push_config.start_message_generator,
                        bound_func, span.args, span.kwargs
                    ))
                    # 保存任务引用，防止被GC回收
                    _background_push_tasks.add(task)
                    # 任务完成后自动移除引用
                    task.add_done_callback(_background_push_tasks.discard)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to execute push on_start hook: {e}", exc_info=True)
    def on_end(span: Span):
        """函数结束时的钩子"""
        if not push_config.push_on_end:
            return
        try:
            if push_config.user_id_getter and push_config.end_message_generator:
                user_id = push_config.user_id_getter(*span.args, **span.kwargs)
                if user_id:
                    # 绑定方法处理
                    bound_func = func
                    if hasattr(func, '__get__') and span.args:
                        bound_func = func.__get__(span.args[0], span.args[0].__class__)
                    # 异步推送
                    task = asyncio.create_task(do_push(
                        push_config, user_id,
                        push_config.end_message_generator,
                        bound_func, span.return_value
                    ))
                    # 保存任务引用，防止被GC回收
                    _background_push_tasks.add(task)
                    # 任务完成后自动移除引用
                    task.add_done_callback(_background_push_tasks.discard)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to execute push on_end hook: {e}", exc_info=True)
    def on_error(span: Span, exc: Exception):
        """函数异常时的钩子"""
        if not push_config.push_on_error:
            return
        try:
            if push_config.user_id_getter and push_config.error_message_generator:
                user_id = push_config.user_id_getter(*span.args, **span.kwargs)
                if user_id:
                    # 绑定方法处理
                    bound_func = func
                    if hasattr(func, '__get__') and span.args:
                        bound_func = func.__get__(span.args[0], span.args[0].__class__)
                    # 异步推送
                    task = asyncio.create_task(do_push(
                        push_config, user_id,
                        push_config.error_message_generator,
                        bound_func, exc
                    ))
                    # 保存任务引用，防止被GC回收
                    _background_push_tasks.add(task)
                    # 任务完成后自动移除引用
                    task.add_done_callback(_background_push_tasks.discard)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to execute push on_error hook: {e}", exc_info=True)
    return TraceHooks(
        on_start=on_start,
        on_end=on_end,
        on_error=on_error
    )
