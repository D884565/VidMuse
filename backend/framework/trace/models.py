import datetime
from sqlalchemy import BigInteger, String, Integer, Numeric, Text, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.store.database.async_database import Base


class Trace(Base):
    """链路追踪模型，对应traces表"""
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="链路唯一标识")
    method: Mapped[str] = mapped_column(String(10), nullable=False, comment="HTTP方法")
    path: Mapped[str] = mapped_column(String(500), nullable=False, comment="请求路径")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="响应状态码")
    duration_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="总耗时(毫秒)")
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="客户端IP")
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户代理")
    request_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="请求头")
    response_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="响应头")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")


class Span(Base):
    """Span模型，对应spans表"""
    __tablename__ = "spans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="所属链路ID")
    span_id: Mapped[str] = mapped_column(String(16), nullable=False, comment="Span唯一标识")
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="父Span ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="函数名/操作名")
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="类名")
    module_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="模块名")
    start_time: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False, comment="开始时间戳(秒)")
    end_time: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False, comment="结束时间戳(秒)")
    duration_ms: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="耗时(毫秒)")
    args: Mapped[dict | list | None] = mapped_column(JSON, nullable=True, comment="位置参数")
    kwargs: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="关键字参数")
    return_value: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True, comment="返回值")
    exception: Mapped[str | None] = mapped_column(Text, nullable=True, comment="异常信息")
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True, comment="调用堆栈")
    meta_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="扩展元数据")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
