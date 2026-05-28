"""add target_duration, voice_type to projects; create conversations table

Revision ID: 005
Revises: 004
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("target_duration", sa.Integer(), nullable=False, server_default="15", comment="目标视频时长(秒)"))
    op.add_column("projects", sa.Column("voice_type", sa.String(50), nullable=False, server_default="zh_female_cancan_mars_bigtts", comment="语音类型"))
    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, comment="user/assistant"),
        sa.Column("content", sa.Text(), nullable=False, comment="消息内容"),
        sa.Column("frame_id", sa.BigInteger(), sa.ForeignKey("frames.id", ondelete="SET NULL"), nullable=True, comment="关联帧ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_conversations_project", "conversations", ["project_id"])


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_column("projects", "voice_type")
    op.drop_column("projects", "target_duration")
