"""流水线执行记录DAO层"""
from typing import List, Optional
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.v1.app.models.pipeline_execution import PipelineExecution, PipelineExecutionStatus


class PipelineDAO:
    """流水线执行记录DAO"""

    @staticmethod
    async def get_paginated_list(
        db: AsyncSession,
        page: int,
        page_size: int,
        status: Optional[PipelineExecutionStatus] = None,
        pipeline_type: Optional[str] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> tuple[List[PipelineExecution], int]:
        """
        分页查询流水线执行列表
        :return: (执行记录列表, 总数量)
        """
        query = select(PipelineExecution)

        # 构建过滤条件
        filters = []
        if status:
            filters.append(PipelineExecution.status == status)
        if pipeline_type:
            filters.append(PipelineExecution.pipeline_type == pipeline_type)
        if keyword:
            filters.append(
                (PipelineExecution.pipeline_name.ilike(f"%{keyword}%")) |
                (PipelineExecution.execution_id.ilike(f"%{keyword}%"))
            )
        if start_time:
            filters.append(PipelineExecution.created_at >= start_time)
        if end_time:
            filters.append(PipelineExecution.created_at <= end_time)

        if filters:
            query = query.where(and_(*filters))

        # 排序：最新的在前
        query = query.order_by(PipelineExecution.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 执行查询
        result = await db.execute(query)
        items = result.scalars().all()

        # 查询总数量
        count_query = select(func.count(PipelineExecution.id)).where(and_(*filters)) if filters else select(func.count(PipelineExecution.id))
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        return items, total

    @staticmethod
    async def get_by_execution_id(db: AsyncSession, execution_id: str) -> Optional[PipelineExecution]:
        """根据执行ID查询记录"""
        query = select(PipelineExecution).where(PipelineExecution.execution_id == execution_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_statistics(db: AsyncSession) -> dict:
        """获取统计数据"""
        # 总数量
        total_query = select(func.count(PipelineExecution.id))
        total_result = await db.execute(total_query)
        total = total_result.scalar_one()

        # 运行中数量
        running_query = select(func.count(PipelineExecution.id)).where(
            PipelineExecution.status == PipelineExecutionStatus.RUNNING
        )
        running_result = await db.execute(running_query)
        running = running_result.scalar_one()

        # 成功数量
        completed_query = select(func.count(PipelineExecution.id)).where(
            PipelineExecution.status == PipelineExecutionStatus.COMPLETED
        )
        completed_result = await db.execute(completed_query)
        completed = completed_result.scalar_one()

        # 成功率
        success_rate = (completed / total * 100) if total > 0 else 0

        # 平均执行时间（最近7天）
        # MySQL专用：使用TIMESTAMPDIFF计算秒数差
        avg_time_query = select(func.avg(
            func.timestampdiff(text('SECOND'), PipelineExecution.created_at, PipelineExecution.completed_at)
        )).where(
            PipelineExecution.status == PipelineExecutionStatus.COMPLETED,
            PipelineExecution.completed_at >= func.date_sub(func.now(), text('INTERVAL 7 DAY'))
        )
        avg_time_result = await db.execute(avg_time_query)
        avg_duration = avg_time_result.scalar_one() or 0

        return {
            "total": total,
            "running": running,
            "success_rate": round(success_rate, 2),
            "avg_duration": round(avg_duration, 2)  # 秒
        }
