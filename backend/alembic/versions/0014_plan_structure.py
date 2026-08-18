"""Add plan_structure field to workouts (structured warmup/reps/cooldown for interval days)

Revision ID: 0014_plan_structure
Revises: 0013_activity_analysis
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_plan_structure'
down_revision = '0013_activity_analysis'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('workouts', sa.Column('plan_structure', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('workouts', 'plan_structure')
