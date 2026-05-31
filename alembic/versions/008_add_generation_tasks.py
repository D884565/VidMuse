"""add generation task progress tables

Revision ID: 008
Revises: 007
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(80), nullable=True),
        sa.Column("current_frame_id", sa.BigInteger(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_generation_tasks_project", "generation_tasks", ["project_id"])
    op.create_index("idx_generation_tasks_celery", "generation_tasks", ["celery_task_id"])
    op.create_index("idx_generation_tasks_trace", "generation_tasks", ["trace_id"])

    op.create_table(
        "generation_task_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), sa.ForeignKey("generation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_name", sa.String(80), nullable=False),
        sa.Column("frame_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_snapshot", sa.JSON(), nullable=True),
        sa.Column("output_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_generation_task_steps_task", "generation_task_steps", ["task_id"])
    op.create_index("idx_generation_task_steps_frame", "generation_task_steps", ["frame_id"])

    op.add_column("frames", sa.Column("error_message", sa.Text(), nullable=True, comment="生成失败原因"))


def downgrade() -> None:
    op.drop_column("frames", "error_message")
    op.drop_index("idx_generation_task_steps_frame", table_name="generation_task_steps")
    op.drop_index("idx_generation_task_steps_task", table_name="generation_task_steps")
    op.drop_table("generation_task_steps")
    op.drop_index("idx_generation_tasks_trace", table_name="generation_tasks")
    op.drop_index("idx_generation_tasks_celery", table_name="generation_tasks")
    op.drop_index("idx_generation_tasks_project", table_name="generation_tasks")
    op.drop_table("generation_tasks")
