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
from sqlalchemy import inspect


revision = "0010_read_seen"
down_revision = "0009_tz_fix"
branch_labels = None
depends_on = None


def upgrade():
    # user_achievements исторически создавалась только через Base.metadata.create_all()
    # в main.py при первом старте приложения, никогда через alembic — на проде это
    # уже произошло, поэтому там таблица есть. На свежей БД (alembic upgrade head
    # без предварительного create_all) следующий op.add_column падал: ALTER TABLE
    # на несуществующую таблицу. Создаём её здесь в исходной форме (без seen —
    # он добавляется тем же способом, что и раньше, сразу ниже).
    inspector = inspect(op.get_bind())
    if "user_achievements" not in inspector.get_table_names():
        op.create_table(
            "user_achievements",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("achievement_key", sa.String(40), nullable=False),
            sa.Column("earned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id"), nullable=True),
        )
        op.create_index("ix_ua_user_key", "user_achievements", ["user_id", "achievement_key"], unique=True)

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
