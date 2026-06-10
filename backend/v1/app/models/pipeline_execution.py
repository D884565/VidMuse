"""流水线执行记录表模型"""
import datetime
import enum
from sqlalchemy import BigInteger, String, Text, Integer, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class PipelineExecutionStatus(str, enum.Enum):
    """流水线执行状态枚举"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


class PipelineExecution(Base):
    """流水线执行记录表"""
    __tablename__ = "pipeline_executions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="执行ID，全局唯一")
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="流水线名称")
    pipeline_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="流水线类型：video/product/video_overall")
    status: Mapped[PipelineExecutionStatus] = mapped_column(String(20), nullable=False, default=PipelineExecutionStatus.PENDING, comment="执行状态")
    current_processor_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前执行到的处理器索引")
    total_processors: Mapped[int] = mapped_column(Integer, nullable=False, comment="总处理器数量")
    input_params: Mapped[dict] = mapped_column(JSON, nullable=False, comment="初始输入参数")
    context_data: Mapped[dict] = mapped_column(JSON, nullable=True, comment="上下文数据快照")
    context_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, comment="上下文元数据快照")
    errors: Mapped[list] = mapped_column(JSON, nullable=True, comment="错误信息列表")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最后一次错误信息")
    result: Mapped[dict] = mapped_column(JSON, nullable=True, comment="最终执行结果")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_type": self.pipeline_type,
            "status": self.status,
            "current_processor_index": self.current_processor_index,
            "total_processors": self.total_processors,
            "input_params": self.input_params,
            "context_data": self.context_data,
            "context_metadata": self.context_metadata,
            "errors": self.errors,
            "error_message": self.error_message,
            "result": self.result,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
        }
