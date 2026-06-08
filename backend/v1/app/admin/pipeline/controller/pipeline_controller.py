"""流水线管理API接口"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.store.database.async_database import get_db
from backend.framework.web.response import Response
from backend.framework.web.auth import admin_required
from backend.v1.app.admin.pipeline.service.pipeline_service import PipelineService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pipelines", tags=["admin-pipelines"])
pipeline_service = PipelineService()


# 请求参数验证
class RetryPipelineRequest(BaseModel):
    """重试流水线请求"""
    force: Optional[bool] = Field(False, description="是否强制重试")


@router.get("/", summary="分页查询流水线执行列表")
async def list_pipelines(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="执行状态：pending/running/completed/failed/cancelled"),
    pipeline_type: Optional[str] = Query(None, description="流水线类型"),
    keyword: Optional[str] = Query(None, description="关键词搜索（名称/ID）"),
    start_time: Optional[int] = Query(None, description="开始时间（时间戳）"),
    end_time: Optional[int] = Query(None, description="结束时间（时间戳）"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    items, total = await pipeline_service.get_pipeline_list(
        db, page, page_size, status, pipeline_type, keyword, start_time, end_time
    )
    return Response.success(data={
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/statistics", summary="获取流水线统计数据")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    stats = await pipeline_service.get_statistics(db)
    return Response.success(data=stats)


@router.get("/{execution_id}", summary="获取流水线执行详情")
async def get_pipeline_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    detail = await pipeline_service.get_pipeline_detail(db, execution_id)
    if not detail:
        return Response.error(message="流水线执行记录不存在")
    return Response.success(data=detail)


@router.post("/{execution_id}/retry", summary="重试失败的流水线")
async def retry_pipeline(
    execution_id: str,
    request: Optional[RetryPipelineRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    force = request.force if request else False
    success = await pipeline_service.retry_pipeline(db, execution_id, force)
    if success:
        return Response.success(message="流水线已提交重试")
    return Response.error(message="重试失败")


@router.post("/{execution_id}/cancel", summary="取消正在执行的流水线")
async def cancel_pipeline(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(admin_required),
):
    success = await pipeline_service.cancel_pipeline(db, execution_id)
    if success:
        return Response.success(message="流水线已取消")
    return Response.error(message="取消失败")
