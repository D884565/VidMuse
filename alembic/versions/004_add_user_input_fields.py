"""add user input fields to projects

Revision ID: 004
Revises: 003
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("user_prompt", sa.Text(), nullable=True, comment="用户创作意图"))
    op.add_column("projects", sa.Column("reference_images", sa.JSON(), nullable=True, comment="参考图片URL列表"))
    op.add_column("projects", sa.Column("style", sa.String(50), nullable=True, comment="视频风格"))
    op.add_column("projects", sa.Column("target_audience", sa.String(100), nullable=True, comment="目标受众"))
    op.add_column("projects", sa.Column("key_points", sa.JSON(), nullable=True, comment="强调卖点列表"))
    op.add_column("projects", sa.Column("avoid", sa.JSON(), nullable=True, comment="避免内容列表"))
    op.add_column("projects", sa.Column("rag_weight", sa.Numeric(3, 2), nullable=False, server_default="0.30", comment="RAG权重"))


def downgrade() -> None:
    op.drop_column("projects", "rag_weight")
    op.drop_column("projects", "avoid")
    op.drop_column("projects", "key_points")
    op.drop_column("projects", "target_audience")
    op.drop_column("projects", "style")
    op.drop_column("projects", "reference_images")
    op.drop_column("projects", "user_prompt")
