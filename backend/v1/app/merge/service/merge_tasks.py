"""持久化合并任务的 Celery Worker。"""
import asyncio

from backend.v1.app.generate.temp.celery_app import celery_app
from backend.v1.app.merge.service.merge_service import merge_service


@celery_app.task(bind=True, name="merge_replace_audio_task", soft_time_limit=1800, time_limit=2100)
def merge_replace_audio_task(self, task_id: str):
    asyncio.run(merge_service.run_dispatched_task(task_id))


@celery_app.task(bind=True, name="merge_add_bgm_task", soft_time_limit=1800, time_limit=2100)
def merge_add_bgm_task(self, task_id: str):
    asyncio.run(merge_service.run_dispatched_task(task_id))


@celery_app.task(bind=True, name="merge_mix_audio_task", soft_time_limit=1800, time_limit=2100)
def merge_mix_audio_task(self, task_id: str):
    asyncio.run(merge_service.run_dispatched_task(task_id))
