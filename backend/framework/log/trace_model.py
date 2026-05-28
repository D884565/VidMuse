"""链路追踪数据模型"""
import datetime
from sqlalchemy import String, BigInteger, Integer, DateTime, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class TraceLog(Base):
    """每次 HTTP 请求的链路追踪记录"""
    __tablename__ = "trace_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="请求唯一标识")
    method: Mapped[str] = mapped_column(String(10), nullable=False, comment="HTTP 方法")
    path: Mapped[str] = mapped_column(String(500), nullable=False, comment="请求路径")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="响应状态码")
    duration_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="请求耗时(毫秒)")
    span_tree: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="span 调用链树")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
