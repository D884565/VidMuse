"""任务调度API控制器"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from backend.store.database.async_database import get_db
from backend.v1.app.task_scheduler.dto.task_schema import (
    TaskSubmitRequest, TaskSubmitResponse, TaskStatusResponse, TaskCancelResponse
)
from backend.v1.app.task_scheduler.service.task_service import task_service

router = APIRouter(prefix="/api/v1/tasks", tags=["任务调度"])


@router.post("/submit", response_model=TaskSubmitResponse, summary="提交任务")
async def submit_task(
    task_request: TaskSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    """提交异步任务到调度队列"""
    result = await task_service.submit_task(db, task_request)
    return result


@router.get("/{task_id}", response_model=Optional[TaskStatusResponse], summary="查询任务状态")
async def get_task_status(task_id: str):
    """根据任务ID查询任务执行状态"""
    return await task_service.get_task_status(task_id)


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse, summary="取消任务")
async def cancel_task(
    task_id: str,
    user_id: Optional[int] = Query(None, description="操作用户ID"),
    db: AsyncSession = Depends(get_db)
):
    """取消指定的排队中或执行中的任务"""
    return await task_service.cancel_task(db, task_id, user_id)
