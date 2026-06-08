"""流水线状态推送服务"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.v1.app.push.service.push_service import PushService
from backend.v1.app.models.pipeline_execution import PipelineExecution
import logging

logger = logging.getLogger(__name__)


class PipelinePushService:
    """流水线状态推送服务"""

    def __init__(self):
        self.push_service = PushService()

    async def push_execution_update(self, db: Session, execution: PipelineExecution) -> None:
        """
        推送流水线执行状态更新
        :param execution: 流水线执行记录对象
        """
        try:
            # 计算进度百分比
            progress = 0
            if execution.total_processors > 0:
                progress = int((execution.current_processor_index / execution.total_processors) * 100)
                # 完成时进度设为100%
                if execution.status in ["completed", "failed", "cancelled"]:
                    progress = 100

            # 构建消息内容
            content = {
                "execution_id": execution.execution_id,
                "pipeline_name": execution.pipeline_name,
                "pipeline_type": execution.pipeline_type,
                "status": execution.status,
                "current_processor_index": execution.current_processor_index,
                "total_processors": execution.total_processors,
                "progress": progress,
                "error_message": execution.error_message,
                "updated_at": execution.updated_at.isoformat() + "Z" if execution.updated_at else None
            }

            # 推送消息给所有管理员
            await self.push_service.push_to_admin(
                db=db,
                message_type="pipeline_execution_update",
                title=f"流水线{execution.status}",
                content=content,
                level="info" if execution.status not in ["failed", "cancelled"] else "warning",
                trace_id=execution.execution_id
            )

            logger.debug(f"已推送流水线状态更新: {execution.execution_id}, 状态: {execution.status}")

        except Exception as e:
            logger.error(f"推送流水线状态更新失败: {str(e)}", exc_info=True)
