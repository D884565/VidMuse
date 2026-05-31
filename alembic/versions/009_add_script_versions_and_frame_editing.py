"""add script versions and frame editing fields

Revision ID: 009
Revises: 008
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scripts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("generation_mode", sa.String(30), nullable=False, server_default="llm"),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=True),
        sa.Column("rag_snapshot", sa.JSON(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("scripts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_scripts_project", "scripts", ["project_id"])
    op.create_index("idx_scripts_project_version", "scripts", ["project_id", "version"], unique=True)

    op.add_column("frames", sa.Column("script_id", sa.BigInteger(), nullable=True))
    op.add_column("frames", sa.Column("narration", sa.Text(), nullable=True))
    op.add_column("frames", sa.Column("subtitle_text", sa.String(500), nullable=True))
    op.add_column("frames", sa.Column("subtitle_position", sa.String(30), nullable=True))
    op.add_column("frames", sa.Column("image_prompt", sa.Text(), nullable=True))
    op.add_column("frames", sa.Column("video_prompt", sa.Text(), nullable=True))
    op.add_column("frames", sa.Column("dirty", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("frames", sa.Column("last_edited_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_frames_script_id_scripts",
        "frames",
        "scripts",
        ["script_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_frames_script", "frames", ["script_id"])


def downgrade() -> None:
    op.drop_index("idx_frames_script", table_name="frames")
    op.drop_constraint("fk_frames_script_id_scripts", "frames", type_="foreignkey")
    op.drop_column("frames", "last_edited_at")
    op.drop_column("frames", "dirty")
    op.drop_column("frames", "video_prompt")
    op.drop_column("frames", "image_prompt")
    op.drop_column("frames", "subtitle_position")
    op.drop_column("frames", "subtitle_text")
    op.drop_column("frames", "narration")
    op.drop_column("frames", "script_id")
    op.drop_index("idx_scripts_project_version", table_name="scripts")
    op.drop_index("idx_scripts_project", table_name="scripts")
    op.drop_table("scripts")
