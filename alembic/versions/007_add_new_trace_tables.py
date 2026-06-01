"""add new trace tables

Revision ID: 007_add_new_trace_tables
Revises:
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_new_trace_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create traces table
    op.create_table(
        'traces',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trace_id', sa.String(length=32), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('client_ip', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_headers', sa.JSON(), nullable=True),
        sa.Column('response_headers', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trace_id', name='uq_traces_trace_id')
    )

    # Add indexes for traces
    op.create_index('idx_trace_created_at', 'traces', ['created_at'], unique=False)
    op.create_index('idx_trace_path', 'traces', ['path'], unique=False)

    # Create spans table
    op.create_table(
        'spans',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trace_id', sa.String(length=32), nullable=False),
        sa.Column('span_id', sa.String(length=16), nullable=False),
        sa.Column('parent_span_id', sa.String(length=16), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('class_name', sa.String(length=255), nullable=True),
        sa.Column('module_name', sa.String(length=255), nullable=False),
        sa.Column('start_time', sa.DECIMAL(precision=16, scale=6), nullable=False),
        sa.Column('end_time', sa.DECIMAL(precision=16, scale=6), nullable=False),
        sa.Column('duration_ms', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('args', sa.JSON(), nullable=True),
        sa.Column('kwargs', sa.JSON(), nullable=True),
        sa.Column('return_value', sa.JSON(), nullable=True),
        sa.Column('exception', sa.Text(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for spans
    op.create_index('idx_span_trace_id', 'spans', ['trace_id'], unique=False)
    op.create_index('idx_span_parent_id', 'spans', ['parent_span_id'], unique=False)
    op.create_index('idx_span_name', 'spans', ['name'], unique=False)
    op.create_index('idx_span_created_at', 'spans', ['created_at'], unique=False)


def downgrade():
    # Drop spans table and indexes first
    op.drop_index('idx_span_name', table_name='spans')
    op.drop_index('idx_span_parent_id', table_name='spans')
    op.drop_index('idx_span_trace_id', table_name='spans')
    op.drop_index('idx_span_created_at', table_name='spans')
    op.drop_table('spans')

    # Drop traces indexes and table
    op.drop_index('idx_trace_path', table_name='traces')
    op.drop_index('idx_trace_created_at', table_name='traces')
    op.drop_table('traces')
