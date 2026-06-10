import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.store.database.async_database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="消息角色: user/assistant")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息文本内容")
    message_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="text",
        server_default="text",
        comment="消息类型: text/stage_card/progress/asset",
    )
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="关联工作流阶段")
    blocks: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="结构化消息块")
    action_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="动作类型")
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="关联任务 ID")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, comment="额外元数据")
    frame_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("frames.id", ondelete="SET NULL"), nullable=True, comment="关联分镜 ID"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="conversations")
