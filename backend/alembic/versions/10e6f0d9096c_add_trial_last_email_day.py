"""add_trial_last_email_day

Revision ID: 10e6f0d9096c
Revises: 0003_activity_details
Create Date: 2026-06-09 06:42:28.553276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '10e6f0d9096c'
down_revision: Union[str, Sequence[str], None] = '0003_activity_details'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('trial_last_email_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'trial_last_email_day')
