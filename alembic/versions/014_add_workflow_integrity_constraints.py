"""add workflow integrity constraints

Revision ID: 014
Revises: 013
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_frames_project_id", "frames", ["project_id"], unique=False)
    op.create_unique_constraint("uq_frames_project_sequence", "frames", ["project_id", "sequence"])
    op.create_unique_constraint("uq_scripts_project_version", "scripts", ["project_id", "version"])
    op.create_unique_constraint(
        "uq_project_assets_project_asset_role",
        "project_assets",
        ["project_id", "asset_id", "role"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_project_assets_project_asset_role", "project_assets", type_="unique")
    op.drop_constraint("uq_scripts_project_version", "scripts", type_="unique")
    op.drop_constraint("uq_frames_project_sequence", "frames", type_="unique")
    op.drop_index("ix_frames_project_id", table_name="frames")
