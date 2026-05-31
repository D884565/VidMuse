"""流水线执行记录数据访问层"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import datetime

from backend.v1.app.models.pipeline_execution import PipelineExecution, PipelineExecutionStatus


class PipelineExecutionDAO:
    """流水线执行记录数据访问层"""

    @staticmethod
    def generate_execution_id() -> str:
        """生成全局唯一的执行ID"""
        return f"exec_{uuid.uuid4().hex[:24]}"

    @staticmethod
    def create_execution(db: Session,
                        pipeline_name: str,
                        pipeline_type: str,
                        input_params: dict,
                        total_processors: int) -> PipelineExecution:
        """创建新的执行记录"""
        execution = PipelineExecution(
            execution_id=PipelineExecutionDAO.generate_execution_id(),
            pipeline_name=pipeline_name,
            pipeline_type=pipeline_type,
            status=PipelineExecutionStatus.PENDING,
            current_processor_index=-1,  # 还未开始执行
            total_processors=total_processors,
            input_params=input_params,
            context_data={},
            context_metadata={},
            errors=[]
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    @staticmethod
    def get_execution_by_id(db: Session, execution_id: str) -> Optional[PipelineExecution]:
        """根据执行ID查询执行记录"""
        return db.query(PipelineExecution).filter(PipelineExecution.execution_id == execution_id).first()

    @staticmethod
    def get_executions_by_pipeline_type(db: Session, pipeline_type: str, limit: int = 100) -> List[PipelineExecution]:
        """根据流水线类型查询执行记录，按创建时间倒序"""
        return db.query(PipelineExecution)\
            .filter(PipelineExecution.pipeline_type == pipeline_type)\
            .order_by(PipelineExecution.created_at.desc())\
            .limit(limit)\
            .all()

    @staticmethod
    def get_failed_executions(db: Session, limit: int = 100) -> List[PipelineExecution]:
        """查询失败的执行记录，按创建时间倒序"""
        return db.query(PipelineExecution)\
            .filter(PipelineExecution.status == PipelineExecutionStatus.FAILED)\
            .order_by(PipelineExecution.created_at.desc())\
            .limit(limit)\
            .all()

    @staticmethod
    def update_execution_status(db: Session,
                               execution_id: str,
                               status: PipelineExecutionStatus,
                               error_message: Optional[str] = None) -> Optional[PipelineExecution]:
        """更新执行状态"""
        update_data = {
            "status": status,
            "updated_at": func.now()
        }
        if error_message:
            update_data["error_message"] = error_message
        if status == PipelineExecutionStatus.COMPLETED:
            update_data["completed_at"] = func.now()

        db.query(PipelineExecution)\
            .filter(PipelineExecution.execution_id == execution_id)\
            .update(update_data)
        db.commit()
        return PipelineExecutionDAO.get_execution_by_id(db, execution_id)

    @staticmethod
    def update_execution_progress(db: Session,
                                 execution_id: str,
                                 current_processor_index: int,
                                 context_data: dict,
                                 context_metadata: dict,
                                 errors: List[str]) -> Optional[PipelineExecution]:
        """更新执行进度和上下文数据"""
        db.query(PipelineExecution)\
            .filter(PipelineExecution.execution_id == execution_id)\
            .update({
                "current_processor_index": current_processor_index,
                "context_data": context_data,
                "context_metadata": context_metadata,
                "errors": errors,
                "updated_at": func.now()
            })
        db.commit()
        return PipelineExecutionDAO.get_execution_by_id(db, execution_id)

    @staticmethod
    def update_execution_result(db: Session,
                               execution_id: str,
                               result: dict) -> Optional[PipelineExecution]:
        """更新执行结果"""
        db.query(PipelineExecution)\
            .filter(PipelineExecution.execution_id == execution_id)\
            .update({
                "result": result,
                "updated_at": func.now()
            })
        db.commit()
        return PipelineExecutionDAO.get_execution_by_id(db, execution_id)

    @staticmethod
    def delete_execution(db: Session, execution_id: str) -> int:
        """删除执行记录，返回删除的数量"""
        result = db.query(PipelineExecution)\
            .filter(PipelineExecution.execution_id == execution_id)\
            .delete()
        db.commit()
        return result

    @staticmethod
    def cleanup_old_executions(db: Session, days: int = 7) -> int:
        """清理N天前的执行记录，返回删除的数量"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        result = db.query(PipelineExecution)\
            .filter(PipelineExecution.created_at < cutoff_date)\
            .delete()
        db.commit()
        return result
