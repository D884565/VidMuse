"""Celery 应用初始化"""
from celery import Celery
from backend.v1.app.config.config import settings

celery_app = Celery(
    "vidmuse",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "backend.v1.app.generate.tasks.video_tasks",
        "backend.v1.app.merge.service.merge_tasks",
    ],
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
)
