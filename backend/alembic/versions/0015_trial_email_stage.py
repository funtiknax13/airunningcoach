"""Rename trial_last_email_day -> trial_last_email_stage (48h trial checkpoints, not calendar days)

Revision ID: 0015_trial_email_stage
Revises: 0014_plan_structure
Create Date: 2026-08-20
"""
from alembic import op

revision = '0015_trial_email_stage'
down_revision = '0014_plan_structure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'trial_last_email_day', new_column_name='trial_last_email_stage')


def downgrade() -> None:
    op.alter_column('users', 'trial_last_email_stage', new_column_name='trial_last_email_day')
