"""对话历史模型"""
import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="user/assistant")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    frame_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("frames.id", ondelete="SET NULL"), nullable=True, comment="关联帧ID"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    project = relationship("Project", back_populates="conversations")
