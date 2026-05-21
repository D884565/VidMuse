"""初始化数据库：projects / scripts / materials 三表

迁移 ID: 001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False, comment="项目标题"),
        sa.Column("description", sa.Text(), nullable=True, comment="项目描述"),
        sa.Column("product_url", sa.String(1000), nullable=True, comment="商品链接"),
        sa.Column("product_image", sa.String(500), nullable=True, comment="商品主图URL"),
        sa.Column("product_info", sa.Text(), nullable=True, comment="商品信息JSON"),
        sa.Column("video_output_url", sa.String(500), nullable=True, comment="最终成片URL"),
        sa.Column("status", sa.String(20), nullable=False, default="draft",
                  comment="draft/script_ready/processing/completed/failed"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Index("idx_created_at", "created_at"),
        sa.Index("idx_status", "status"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="视频项目表",
    )

    op.create_table(
        "scripts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, comment="所属项目"),
        sa.Column("title", sa.String(200), nullable=True, comment="剧本标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="剧本JSON内容"),
        sa.Column("target_duration", sa.Integer(), nullable=True, comment="目标时长(秒)"),
        sa.Column("ai_model", sa.String(50), nullable=True, comment="使用的AI模型"),
        sa.Column("ai_prompt", sa.Text(), nullable=True, comment="生成使用的完整Prompt"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="剧本表",
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=True, comment="所属项目"),
        sa.Column("script_id", sa.BigInteger(), sa.ForeignKey("scripts.id", ondelete="SET NULL"),
                  nullable=True, comment="所属剧本段落"),
        sa.Column("type", sa.Integer(), nullable=False,
                  comment="1=商品图 2=背景音乐 3=配音 4=字幕 5=成品视频"),
        sa.Column("title", sa.String(200), nullable=True, comment="素材标题"),
        sa.Column("url", sa.String(500), nullable=False, comment="MinIO路径"),
        sa.Column("file_size", sa.BigInteger(), nullable=True, comment="文件大小(字节)"),
        sa.Column("duration", sa.Integer(), nullable=True, comment="时长(秒)"),
        sa.Column("format", sa.String(20), nullable=True, comment="文件格式"),
        sa.Column("ai_features", sa.Text(), nullable=True, comment="AI特征JSON"),
        sa.Column("source_type", sa.Integer(), default=0, comment="0=上传 1=AI生成 2=模板"),
        sa.Column("scene_index", sa.Integer(), nullable=True, comment="场景序号"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("idx_project", "project_id"),
        sa.Index("idx_type", "type"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        comment="素材表",
    )


def downgrade() -> None:
    op.drop_table("materials")
    op.drop_table("scripts")
    op.drop_table("projects")
