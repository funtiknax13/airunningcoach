"""add payments table

Revision ID: 0006_payments
Revises: 0005_strava_fields
Create Date: 2026-06-12 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_payments"
down_revision = "0005_strava_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id",          sa.Integer(),     primary_key=True),
        sa.Column("user_id",     sa.Integer(),     sa.ForeignKey("users.id"), nullable=False),
        sa.Column("yookassa_id", sa.String(64),    nullable=False, unique=True),
        sa.Column("plan",        sa.String(20),    nullable=False),
        sa.Column("amount",      sa.Integer(),     nullable=False),
        sa.Column("status",      sa.String(20),    server_default="pending"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("paid_at",     sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_user_id",     "payments", ["user_id"])
    op.create_index("ix_payments_yookassa_id", "payments", ["yookassa_id"], unique=True)


def downgrade():
    op.drop_table("payments")
