"""视频帧模型"""
import datetime
from sqlalchemy import (
    String, Text, BigInteger, Integer, DateTime, Numeric, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.store.database.async_database import Base


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="帧id")
    project_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="项目id"
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, comment="帧序号(第几帧)")
    scene_type: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="场景类型: 0-开场, 1-商品展示, 2-口播, 3-转场, 4-结尾"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="帧描述/画面描述")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="生成该帧的AI提示词")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="帧图片URL")
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="帧配音/音效URL")
    text_overlay: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="叠加文字内容")
    duration: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, server_default="3.000",
        comment="该帧持续时间(秒)"
    )
    transition_type: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
        comment="转场类型: 0-无, 1-淡入, 2-滑动, 3-缩放"
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
        comment="状态: 0-待生成, 1-生成中, 2-已完成, 3-失败"
    )
    ai_params: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI生成参数")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True, comment="额外元数据")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关联
    project = relationship("Project", back_populates="frames")
