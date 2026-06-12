"""add activity_type to activities

Revision ID: 0005_strava_fields
Revises: 10e6f0d9096c
Create Date: 2026-06-11 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_strava_fields"
down_revision = "10e6f0d9096c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activities", sa.Column("activity_type", sa.String(50), nullable=True, server_default="run"))


def downgrade():
    op.drop_column("activities", "activity_type")
