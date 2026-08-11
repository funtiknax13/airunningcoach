"""support tickets: support_tickets + support_messages

Тикет-система поддержки (тред «пользователь ↔ поддержка», статусы open/closed,
общий инбокс). Заменяет прежнюю поддержку через письмо админам.

status — VARCHAR (не native enum), чтобы добавлять значения без ALTER TYPE.
created_by_user_id / sender_user_id — nullable + ON DELETE SET NULL: удаление
аккаунта не рушит историю обращений.

Revision ID: 0011_support_tickets
Revises: 0010_read_seen
Create Date: 2026-08-11 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0011_support_tickets"
down_revision = "0010_read_seen"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_support_tickets_created_by_user_id", "support_tickets", ["created_by_user_id"])

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id", sa.Integer(),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "sender_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])


def downgrade():
    op.drop_index("ix_support_messages_ticket_id", "support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_created_by_user_id", "support_tickets")
    op.drop_table("support_tickets")
