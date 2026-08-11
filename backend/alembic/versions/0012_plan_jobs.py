"""plan_jobs: фоновая генерация длинных планов

Длинный план (месяц/3 месяца) собирается в фоне кусками — строка хранит статус
задачи (running/done/failed), по которому фронт показывает «готовится» и ждёт.

Revision ID: 0012_plan_jobs
Revises: 0011_support_tickets
Create Date: 2026-08-11 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_plan_jobs"
down_revision = "0011_support_tickets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_plan_jobs_user_id", "plan_jobs", ["user_id"])


def downgrade():
    op.drop_index("ix_plan_jobs_user_id", "plan_jobs")
    op.drop_table("plan_jobs")
