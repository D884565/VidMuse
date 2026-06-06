from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from backend.store.database.async_database import Base


class GenerationFrameProgress(Base):
    """帧级生成进度表。"""

    __tablename__ = "generation_frame_progress"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(80), nullable=False, index=True, comment="任务ID")
    project_id = Column(BigInteger, nullable=False, index=True, comment="项目ID")
    frame_id = Column(BigInteger, nullable=False, comment="帧ID")
    stage = Column(String(50), nullable=False, comment="阶段")
    status = Column(String(30), nullable=False, default="pending", index=True, comment="状态")
    attempt_count = Column(Integer, default=0, comment="尝试次数")
    error_message = Column(Text, comment="错误信息")
    result_url = Column(String(500), comment="结果URL")
    started_at = Column(DateTime(timezone=True), comment="开始时间")
    finished_at = Column(DateTime(timezone=True), comment="完成时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"comment": "帧级生成进度表"},
    )
