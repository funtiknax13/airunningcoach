"""add chat_messages.read and user_achievements.seen

Оба поля со server_default='true' — существующие сообщения/достижения
считаются уже просмотренными, новый непрочитанный статус выставляется
только явно в коде для вновь создаваемых фоновых AI-сообщений и вновь
разблокированных достижений.

Revision ID: 0010_read_seen
Revises: 0009_tz_fix
Create Date: 2026-07-24 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_read_seen"
down_revision = "0009_tz_fix"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chat_messages",
        sa.Column("read", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "user_achievements",
        sa.Column("seen", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade():
    op.drop_column("user_achievements", "seen")
    op.drop_column("chat_messages", "read")
