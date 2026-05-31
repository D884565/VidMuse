"""add project workflow fields

Revision ID: 011
Revises: 010
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("workflow_stage", sa.String(30), nullable=False, server_default="created"))
    op.add_column("projects", sa.Column("stage_status", sa.String(30), nullable=False, server_default="idle"))
    op.add_column("projects", sa.Column("last_task_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("dirty_stage", sa.String(30), nullable=True))
    op.add_column("projects", sa.Column("script_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("images_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("projects", sa.Column("video_confirmed_at", sa.DateTime(), nullable=True))
    op.create_index("idx_projects_workflow_status", "projects", ["workflow_stage", "stage_status"])
    op.execute(
        """
        UPDATE projects
        SET
            workflow_stage = CASE
                WHEN status = 'completed' THEN 'completed'
                WHEN status IN ('render_queued', 'rendering', 'processing') THEN 'video'
                WHEN status IN ('script_ready', 'review_required') THEN 'script'
                WHEN status = 'script_generating' THEN 'script'
                WHEN status = 'failed' THEN 'script'
                ELSE 'created'
            END,
            stage_status = CASE
                WHEN status = 'completed' THEN 'confirmed'
                WHEN status IN ('render_queued', 'rendering', 'processing', 'script_generating') THEN 'running'
                WHEN status IN ('script_ready', 'review_required') THEN 'awaiting_review'
                WHEN status = 'failed' THEN 'failed'
                ELSE 'idle'
            END
        """
    )


def downgrade() -> None:
    op.drop_index("idx_projects_workflow_status", table_name="projects")
    op.drop_column("projects", "video_confirmed_at")
    op.drop_column("projects", "images_confirmed_at")
    op.drop_column("projects", "script_confirmed_at")
    op.drop_column("projects", "dirty_stage")
    op.drop_column("projects", "last_task_id")
    op.drop_column("projects", "stage_status")
    op.drop_column("projects", "workflow_stage")
