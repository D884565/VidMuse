"""添加 frames 表，projects 表加 audio_url

Revision ID: 003
Revises: 002
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # projects 表加 audio_url 字段
    op.add_column("projects", sa.Column("audio_url", sa.String(500), nullable=True, comment="TTS配音音频URL"))

    # 创建 frames 表
    op.create_table(
        "frames",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True, comment="帧id"),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目id"),
        sa.Column("sequence", sa.Integer, nullable=False, comment="帧序号"),
        sa.Column("scene_type", sa.Integer, nullable=True, comment="场景类型: 0-开场, 1-商品展示, 2-口播, 3-转场, 4-结尾"),
        sa.Column("description", sa.Text, nullable=True, comment="帧描述/画面描述"),
        sa.Column("prompt", sa.Text, nullable=True, comment="AI提示词"),
        sa.Column("image_url", sa.String(500), nullable=True, comment="帧图片URL"),
        sa.Column("audio_url", sa.String(500), nullable=True, comment="帧配音URL"),
        sa.Column("text_overlay", sa.String(500), nullable=True, comment="叠加文字"),
        sa.Column("duration", sa.Numeric(6, 3), server_default="3.000", comment="持续时间(秒)"),
        sa.Column("transition_type", sa.Integer, server_default="0", comment="转场类型: 0-无, 1-淡入, 2-滑动, 3-缩放"),
        sa.Column("status", sa.Integer, server_default="0", comment="状态: 0-待生成, 1-生成中, 2-已完成, 3-失败"),
        sa.Column("ai_params", sa.JSON, nullable=True, comment="AI生成参数"),
        sa.Column("metadata", sa.JSON, nullable=True, comment="额外元数据"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_unique_constraint("uk_project_sequence", "frames", ["project_id", "sequence"])
    op.create_index("idx_project_status", "frames", ["project_id", "status"])
    op.create_index("idx_scene_type", "frames", ["scene_type"])


def downgrade() -> None:
    op.drop_table("frames")
    op.drop_column("projects", "audio_url")
