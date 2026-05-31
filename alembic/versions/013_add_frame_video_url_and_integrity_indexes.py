"""add frame video url and integrity indexes

Revision ID: 013
Revises: 012
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 单帧视频产物独立存储，避免继续复用 audio_url 造成语义混乱。
    op.add_column("frames", sa.Column("video_url", sa.String(500), nullable=True, comment="帧视频片段URL"))
    op.execute(
        """
        UPDATE frames
        SET video_url = audio_url,
            audio_url = NULL
        WHERE audio_url IS NOT NULL
          AND (audio_url LIKE '%.mp4%' OR audio_url LIKE '%/frames/frame_%')
        """
    )

    # 这些索引用于高频列表/详情查询；若线上已存在，迁移前需 dry-run 审核。
    op.create_index("idx_projects_status", "projects", ["status"])
    op.create_index("idx_projects_user", "projects", ["user_id"])
    op.create_index("idx_assets_user", "assets", ["user_id"])
    op.create_index("idx_conversations_frame", "conversations", ["frame_id"])


def downgrade() -> None:
    op.drop_index("idx_conversations_frame", table_name="conversations")
    op.drop_index("idx_assets_user", table_name="assets")
    op.drop_index("idx_projects_user", table_name="projects")
    op.drop_index("idx_projects_status", table_name="projects")
    op.drop_column("frames", "video_url")
