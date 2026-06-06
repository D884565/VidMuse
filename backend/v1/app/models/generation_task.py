from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from backend.store.database.async_database import Base


class GenerationTask(Base):
    """生成任务表（阶段级追踪）。"""

    __tablename__ = "generation_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(80), unique=True, nullable=False, index=True, comment="任务ID")
    project_id = Column(BigInteger, nullable=False, index=True, comment="项目ID")
    task_type = Column(String(50), nullable=False, comment="任务类型")
    status = Column(String(30), nullable=False, default="queued", index=True, comment="状态")
    current_stage = Column(String(50), comment="当前阶段")
    progress = Column(Integer, default=0, comment="进度 0-100")
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    error_code = Column(String(100), comment="错误码")
    error_message = Column(Text, comment="错误信息")
    trigger_source = Column(String(50), default="manual", comment="触发来源")
    celery_task_id = Column(String(255), comment="Celery任务ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), comment="开始时间")
    finished_at = Column(DateTime(timezone=True), comment="完成时间")
