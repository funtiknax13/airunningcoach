"""Add last_active_at + utm_source/medium/campaign to users (admin analytics)

Revision ID: 0016_analytics_columns
Revises: 0015_trial_email_stage
Create Date: 2026-08-26
"""
import sqlalchemy as sa
from alembic import op

revision = '0016_analytics_columns'
down_revision = '0015_trial_email_stage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('utm_source', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('utm_medium', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('utm_campaign', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'utm_campaign')
    op.drop_column('users', 'utm_medium')
    op.drop_column('users', 'utm_source')
    op.drop_column('users', 'last_active_at')
