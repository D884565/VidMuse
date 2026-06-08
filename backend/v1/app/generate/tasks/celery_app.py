"""Celery 应用初始化"""
import uuid
import asyncio
from celery import Celery
from celery.schedules import crontab
from backend.v1.app.config.config import settings
from backend.framework.trace.context import trace_id_var, set_user_id, start_span, end_span, get_all_spans, clear_context
from backend.framework.trace.dao import save_trace_data
from backend.framework.trace.decorator import PushConfig

celery_app = Celery(
    "vidmuse",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "backend.v1.app.generate.tasks.video_tasks",
        "backend.v1.app.merge.service.merge_tasks",
        "backend.v1.app.pipeline.tasks.pipeline_tasks",
    ],
)


class BaseTask(celery_app.Task):
    """基础任务类，统一集成Trace和限流"""
    abstract = True

    def __call__(self, *args, **kwargs):
        # 初始化Trace上下文
        trace_id = kwargs.pop('trace_id', None) or uuid.uuid4().hex[:8]
        trace_id_var.set(trace_id)
        user_id = kwargs.get('user_id')
        if user_id:
            set_user_id(user_id)

        # 启动根Span
        span = start_span(
            name=self.name,
            module_name=self.__module__,
            meta_data={
                "task_id": self.request.id,
                "args": args,
                "kwargs": kwargs,
                "user_id": user_id
            }
        )

        try:
            result = super().__call__(*args, **kwargs)
            span.return_value = result
            return result
        except Exception as e:
            span.set_exception(e)
            raise
        finally:
            end_span(span)
            # 异步保存Trace数据
            asyncio.create_task(save_trace_data(
                trace_id=trace_id,
                method="CELERY_TASK",
                path=self.name,
                status_code=200 if not span.exception else 500,
                duration_ms=span.duration_ms,
                user_id=user_id,
                spans=get_all_spans()
            ))
            clear_context()


# 通用任务推送配置
TASK_PUSH_CONFIG = PushConfig(
    enable_push=True,
    user_id_getter=lambda *args, **kwargs: kwargs.get('user_id'),
    push_on_start=True,
    push_on_end=True,
    push_on_error=True,
    start_message_generator=lambda func, args, kwargs: (
        "task_status",
        "任务已开始执行",
        {"task_id": args[0].request.id if hasattr(args[0], 'request') else None},
        "info"
    ),
    end_message_generator=lambda func, result: (
        "task_status",
        "任务执行成功",
        {"task_id": func.request.id if hasattr(func, 'request') else None, "result": result},
        "success"
    ),
    error_message_generator=lambda func, error: (
        "task_status",
        "任务执行失败",
        {"task_id": func.request.id if hasattr(func, 'request') else None, "error": str(error)},
        "error"
    )
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=3600,    # 单任务软限制 60 分钟
    task_time_limit=4500,         # 单任务硬限制 75 分钟
    task_routes={
        'video_production': {'queue': 'video_production', 'routing_key': 'queue.video.production'},
        'video_analysis': {'queue': 'video_analysis', 'routing_key': 'queue.video.analysis'},
        'scheduled_clustering': {'queue': 'scheduled_clustering', 'routing_key': 'queue.scheduled.clustering'},
        '*': {'queue': 'default', 'routing_key': 'queue.default'},
    },
    task_default_queue='default',
    task_default_routing_key='queue.default',
)


# 定时任务配置
celery_app.conf.beat_schedule = {
    # 每日凌晨2点执行向量聚类任务
    'daily-vector-clustering': {
        'task': 'scheduled_clustering',
        'schedule': crontab(hour=2, minute=0),
        'args': ({},),
        'kwargs': {'user_id': None, 'trace_id': None},
        'options': {'queue': 'scheduled_clustering'}
    },
}
