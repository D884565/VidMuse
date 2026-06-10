"""任务调度服务层"""
import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from celery.result import AsyncResult
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.push.service.push_service import push_service
from backend.v1.app.task_scheduler.dto.task_schema import (
    TaskTypeEnum, TaskStatusEnum, TaskSubmitRequest, TaskStatusResponse
)


class TaskService:
    """任务调度服务"""

    TASK_QUEUE_MAPPING = {
        TaskTypeEnum.VIDEO_PRODUCTION: "video_production",
        TaskTypeEnum.VIDEO_ANALYSIS: "video_analysis",
        TaskTypeEnum.SCHEDULED_CLUSTERING: "scheduled_clustering",
        TaskTypeEnum.PRODUCT_PARSING: "pipeline_parsing",
        TaskTypeEnum.DIRECT_VIDEO_PARSING: "pipeline_parsing",
        TaskTypeEnum.DEFAULT: "default"
    }

    @staticmethod
    async def submit_task(
        db: AsyncSession,
        task_request: TaskSubmitRequest
    ) -> Dict[str, Any]:
        """
        提交任务
        :param db: 数据库会话
        :param task_request: 任务提交请求
        :return: 任务信息
        """
        # 生成Trace ID
        trace_id = uuid.uuid4().hex[:8]

        # 确定任务队列
        queue = TaskService.TASK_QUEUE_MAPPING.get(task_request.task_type, "default")

        # 发送Celery任务
        task = celery_app.send_task(
            task_request.task_type.value,
            args=[task_request.payload],
            kwargs={
                "user_id": task_request.user_id,
                "trace_id": trace_id
            },
            queue=queue,
            priority=task_request.priority
        )

        # 推送任务排队通知
        if task_request.user_id:
            await push_service.push_message(
                db=db,
                user_id=task_request.user_id,
                message_type="task_status",
                title="任务已提交",
                content="您的任务已进入排队队列，请耐心等待",
                task_id=task.id,
                task_type=task_request.task_type.value,
                status=TaskStatusEnum.QUEUED.value,
                progress=0,
                trace_id=trace_id,
                persist=True
            )

        return {
            "task_id": task.id,
            "trace_id": trace_id,
            "status": TaskStatusEnum.QUEUED.value,
            "message": "任务已提交，进入排队队列"
        }

    @staticmethod
    async def get_task_status(task_id: str) -> Optional[TaskStatusResponse]:
        """
        查询任务状态
        :param task_id: 任务ID
        :return: 任务状态信息
        """
        try:
            result = AsyncResult(task_id, app=celery_app)

            # 映射Celery状态到自定义状态
            status_mapping = {
                "PENDING": TaskStatusEnum.QUEUED,
                "STARTED": TaskStatusEnum.RUNNING,
                "SUCCESS": TaskStatusEnum.SUCCEEDED,
                "FAILURE": TaskStatusEnum.FAILED,
                "REVOKED": TaskStatusEnum.CANCELLED,
                "RETRY": TaskStatusEnum.RUNNING
            }

            status = status_mapping.get(result.status, TaskStatusEnum.QUEUED)

            # 构建响应
            response = TaskStatusResponse(
                task_id=task_id,
                trace_id="",  # 可从Trace系统查询，此处简化
                task_type=TaskTypeEnum.DEFAULT,  # 可从任务元数据查询，此处简化
                status=status,
                progress=0,  # 可从业务系统查询，此处简化
                error_message=str(result.info) if status == TaskStatusEnum.FAILED else None,
                result=result.result if status == TaskStatusEnum.SUCCEEDED else None
            )

            return response
        except Exception as e:
            return None

    @staticmethod
    async def cancel_task(db: AsyncSession, task_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        取消任务
        :param db: 数据库会话
        :param task_id: 任务ID
        :param user_id: 操作用户ID
        :return: 取消结果
        """
        try:
            # 撤销任务
            celery_app.control.revoke(task_id, terminate=True)

            # 推送取消通知
            if user_id:
                await push_service.push_message(
                    db=db,
                    user_id=user_id,
                    message_type="task_status",
                    title="任务已取消",
                    content="您的任务已被取消",
                    task_id=task_id,
                    status=TaskStatusEnum.CANCELLED.value,
                    progress=0,
                    persist=True
                )

            return {
                "success": True,
                "message": "任务已取消"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"取消任务失败: {str(e)}"
            }


# 全局服务实例
task_service = TaskService()
