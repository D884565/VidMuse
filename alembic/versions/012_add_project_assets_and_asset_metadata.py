"""add project assets and asset metadata

Revision ID: 012
Revises: 011
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("assets", sa.Column("scope", sa.String(30), nullable=False, server_default="library"))
    op.add_column("assets", sa.Column("metadata", sa.JSON(), nullable=True))
    op.create_index("idx_assets_scope", "assets", ["scope"])

    op.create_table("project_assets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="reference"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_project_assets_project", "project_assets", ["project_id"])
    op.create_index("idx_project_assets_asset", "project_assets", ["asset_id"])
    op.create_index("idx_project_assets_unique", "project_assets", ["project_id", "asset_id", "role"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_project_assets_unique", table_name="project_assets")
    op.drop_index("idx_project_assets_asset", table_name="project_assets")
    op.drop_index("idx_project_assets_project", table_name="project_assets")
    op.drop_table("project_assets")
    op.drop_index("idx_assets_scope", table_name="assets")
    op.drop_column("assets", "metadata")
    op.drop_column("assets", "scope")
    op.drop_column("assets", "tags")
