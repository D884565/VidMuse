"""add product categories table and product category fields

Revision ID: 008
Revises: 007
Create Date: 2026-05-29 17:16:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建商品分类表
    op.create_table(
        'product_categories',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='分类ID'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='分类名称'),
        sa.Column('parent_id', sa.BigInteger(), nullable=False, default=0, comment='父分类ID，0表示一级分类'),
        sa.Column('level', sa.SmallInteger(), nullable=False, comment='分类层级：1-一级分类，2-二级分类，3-三级分类'),
        sa.Column('path', sa.String(length=200), nullable=False, comment='分类路径，如"/1/2/3/"，方便查询子树'),
        sa.Column('sort', sa.Integer(), nullable=False, default=0, comment='排序权重，数值越大越靠前'),
        sa.Column('is_deleted', sa.SmallInteger(), nullable=False, default=0, comment='是否删除：0-未删除，1-已删除'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'parent_id', 'is_deleted', name='uk_name_parent'),
        sa.Index('idx_parent_id', 'parent_id'),
        sa.Index('idx_level', 'level'),
        sa.Index('idx_path', 'path'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_comment='商品分类表'
    )

    # 修改商品表，添加分类相关字段
    op.add_column('products', sa.Column('category_id', sa.BigInteger(), nullable=True, comment='关联分类ID，对应product_categories.id'))
    op.add_column('products', sa.Column('category_path', sa.String(length=200), nullable=True, comment='分类路径，冗余存储方便检索，如"/1/2/3/"'))

    # 创建外键约束
    op.create_foreign_key(
        'fk_products_category_id',
        'products',
        'product_categories',
        ['category_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 创建索引
    op.create_index('idx_category_id', 'products', ['category_id'])
    op.create_index('idx_category_path', 'products', ['category_path'])

    # 修改category字段的注释
    op.alter_column(
        'products',
        'category',
        existing_type=sa.String(length=100),
        comment='商品分类（冗余存储三级分类名称）',
        existing_comment='商品分类',
        existing_nullable=True
    )


def downgrade() -> None:
    # 移除商品表的外键和字段
    op.drop_constraint('fk_products_category_id', 'products', type_='foreignkey')
    op.drop_index('idx_category_id', table_name='products')
    op.drop_index('idx_category_path', table_name='products')
    op.drop_column('products', 'category_id')
    op.drop_column('products', 'category_path')

    # 恢复category字段的注释
    op.alter_column(
        'products',
        'category',
        existing_type=sa.String(length=100),
        comment='商品分类',
        existing_comment='商品分类（冗余存储三级分类名称）',
        existing_nullable=True
    )

    # 删除商品分类表
    op.drop_table('product_categories')
