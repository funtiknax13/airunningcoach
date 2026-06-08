"""Add detailed activity fields (laps, splits, track_points, HR, cadence, elevation)

Revision ID: 0003_activity_details
Revises: 0002_premium_and_usage
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_activity_details'
down_revision = '0002_premium_and_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('max_heart_rate', sa.Integer(),  nullable=True))
    op.add_column('activities', sa.Column('avg_cadence',    sa.Integer(),  nullable=True))
    op.add_column('activities', sa.Column('elevation_gain', sa.Float(),    nullable=True))
    op.add_column('activities', sa.Column('laps',         sa.JSON(),       nullable=True))
    op.add_column('activities', sa.Column('splits',       sa.JSON(),       nullable=True))
    op.add_column('activities', sa.Column('track_points', sa.JSON(),       nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'track_points')
    op.drop_column('activities', 'splits')
    op.drop_column('activities', 'laps')
    op.drop_column('activities', 'elevation_gain')
    op.drop_column('activities', 'avg_cadence')
    op.drop_column('activities', 'max_heart_rate')
