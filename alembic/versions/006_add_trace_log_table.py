"""create trace_log table for request tracing

Revision ID: 006
Revises: 005
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trace_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(32), nullable=False, comment="请求唯一标识"),
        sa.Column("method", sa.String(10), nullable=False, comment="HTTP 方法"),
        sa.Column("path", sa.String(500), nullable=False, comment="请求路径"),
        sa.Column("status_code", sa.Integer(), nullable=False, comment="响应状态码"),
        sa.Column("duration_ms", sa.Numeric(10, 2), nullable=False, comment="请求耗时(毫秒)"),
        sa.Column("span_tree", sa.JSON(), nullable=True, comment="span 调用链树"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_trace_log_request_id", "trace_log", ["request_id"])
    op.create_index("idx_trace_log_created_at", "trace_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("trace_log")
