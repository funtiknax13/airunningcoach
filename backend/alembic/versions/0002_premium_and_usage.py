"""Add premium fields and api_usage table

Revision ID: 0002_premium_and_usage
Revises: 0001_initial_schema
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_premium_and_usage'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем премиум-поля в users
    op.add_column('users', sa.Column('is_premium',    sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('premium_until', sa.DateTime(timezone=True), nullable=True))

    # Таблица для rate limiting
    op.create_table(
        'api_usage',
        sa.Column('id',         sa.Integer(),               nullable=False),
        sa.Column('user_id',    sa.Integer(),               nullable=False),
        sa.Column('action',     sa.String(20),              nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_api_usage_id',      'api_usage', ['id'])
    op.create_index('ix_api_usage_user_id', 'api_usage', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_api_usage_user_id', table_name='api_usage')
    op.drop_index('ix_api_usage_id',      table_name='api_usage')
    op.drop_table('api_usage')
    op.drop_column('users', 'premium_until')
    op.drop_column('users', 'is_premium')
