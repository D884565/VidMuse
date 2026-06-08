"""流水线管理Service层"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from backend.v1.app.admin.pipeline.dao.pipeline_dao import PipelineDAO
from backend.v1.app.models.pipeline_execution import PipelineExecution, PipelineExecutionStatus
from backend.framework.exceptions.exceptions import BusinessException

logger = logging.getLogger(__name__)


class PipelineService:
    """流水线管理Service"""

    def __init__(self):
        self.dao = PipelineDAO()

    async def get_pipeline_list(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
        status: Optional[str] = None,
        pipeline_type: Optional[str] = None,
        keyword: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> tuple[List[dict], int]:
        """获取流水线执行列表"""
        # 转换状态枚举
        status_enum = None
        if status:
            try:
                status_enum = PipelineExecutionStatus(status)
            except ValueError:
                raise BusinessException(message="无效的状态值")

        # 转换时间戳为datetime
        start_datetime = datetime.fromtimestamp(start_time) if start_time else None
        end_datetime = datetime.fromtimestamp(end_time) if end_time else None

        items, total = await self.dao.get_paginated_list(
            db, page, page_size, status_enum, pipeline_type, keyword, start_datetime, end_datetime
        )

        return [item.to_dict() for item in items], total

    async def get_pipeline_detail(self, db: AsyncSession, execution_id: str) -> Optional[dict]:
        """获取流水线执行详情"""
        item = await self.dao.get_by_execution_id(db, execution_id)
        return item.to_dict() if item else None

    async def get_statistics(self, db: AsyncSession) -> dict:
        """获取统计数据"""
        return await self.dao.get_statistics(db)

    async def retry_pipeline(self, db: AsyncSession, execution_id: str, force: bool = False) -> bool:
        """重试失败的流水线"""
        # TODO: 集成流水线执行器的重试逻辑
        # 此处为占位，后续根据实际流水线执行器实现
        item = await self.dao.get_by_execution_id(db, execution_id)
        if not item:
            raise BusinessException(message="流水线执行记录不存在")
        if item.status != PipelineExecutionStatus.FAILED:
            raise BusinessException(message="只有失败的流水线才能重试")

        # 模拟重试逻辑
        item.status = PipelineExecutionStatus.PENDING
        item.current_processor_index = 0
        item.error_message = None
        item.errors = None
        await db.commit()

        logger.info(f"流水线 {execution_id} 已标记为重试，force={force}")
        return True

    async def cancel_pipeline(self, db: AsyncSession, execution_id: str) -> bool:
        """取消正在执行的流水线"""
        # TODO: 集成流水线执行器的取消逻辑
        # 此处为占位，后续根据实际流水线执行器实现
        item = await self.dao.get_by_execution_id(db, execution_id)
        if not item:
            raise BusinessException(message="流水线执行记录不存在")
        if item.status not in [PipelineExecutionStatus.PENDING, PipelineExecutionStatus.RUNNING]:
            raise BusinessException(message="只有待执行或运行中的流水线才能取消")

        # 模拟取消逻辑
        item.status = PipelineExecutionStatus.CANCELLED
        await db.commit()

        logger.info(f"流水线 {execution_id} 已取消")
        return True
