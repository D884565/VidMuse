"""extend conversations for workflow messages

Revision ID: 010
Revises: 009
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("message_type", sa.String(30), nullable=False, server_default="text"))
    op.add_column("conversations", sa.Column("stage", sa.String(30), nullable=True))
    op.add_column("conversations", sa.Column("blocks", sa.JSON(), nullable=True))
    op.add_column("conversations", sa.Column("action_type", sa.String(50), nullable=True))
    op.add_column("conversations", sa.Column("task_id", sa.BigInteger(), nullable=True))
    op.add_column("conversations", sa.Column("metadata", sa.JSON(), nullable=True))
    op.create_index("idx_conversations_task", "conversations", ["task_id"])
    op.create_index("idx_conversations_project_created", "conversations", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_conversations_project_created", table_name="conversations")
    op.drop_index("idx_conversations_task", table_name="conversations")
    op.drop_column("conversations", "metadata")
    op.drop_column("conversations", "task_id")
    op.drop_column("conversations", "action_type")
    op.drop_column("conversations", "blocks")
    op.drop_column("conversations", "stage")
    op.drop_column("conversations", "message_type")
