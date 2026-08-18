"""Add activity_analysis field (interval detection, activity type, negative split, HR decoupling)

Revision ID: 0013_activity_analysis
Revises: 0012_plan_jobs
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_activity_analysis'
down_revision = '0012_plan_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('analysis', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'analysis')
