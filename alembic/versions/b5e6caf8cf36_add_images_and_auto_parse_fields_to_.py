"""add images and auto_parse fields to product

Revision ID: b5e6caf8cf36
Revises: 009
Create Date: 2026-05-31 02:20:47.932103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e6caf8cf36'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加images字段
    op.add_column('products', sa.Column('images', sa.Text(), nullable=True, comment='商品图片URL列表，JSON数组格式'))
    # 添加auto_parse字段，默认值为False
    op.add_column('products', sa.Column('auto_parse', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='是否创建后自动触发解析'))


def downgrade() -> None:
    # 删除字段
    op.drop_column('products', 'auto_parse')
    op.drop_column('products', 'images')
