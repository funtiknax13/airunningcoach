"""fix activities.date to store timezone + add users.timezone

activities.date хранился как timestamp БЕЗ таймзоны, хотя парсеры (GPX/FIT)
всегда отдают корректный UTC. При записи метка молча терялась, а при чтении
API отдавал время без суффикса Z — фронтенд трактовал его как уже локальное,
не пересчитывая. Для бегуна не в UTC+0 это сдвигало отображаемое время
тренировки и час, по которому считаются бейджи вроде «Ранняя пташка»/
«Полуночник».

Существующие значения уже хранят верные UTC-числа (парсеры всегда отдавали
aware UTC-datetime до записи) — просто помечаем колонку как timestamptz,
без пересчёта чисел.

users.timezone — IANA-имя часового пояса пользователя (напр.
Asia/Yekaterinburg), нужен для расчёта бейджей и статистики по локальному
времени, а не по времени сервера.

Revision ID: 0009_tz_fix
Revises: 0008_flatten_workouts
Create Date: 2026-07-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_tz_fix"
down_revision = "0008_flatten_workouts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("timezone", sa.String(length=50), nullable=True))
    op.execute(
        "ALTER TABLE activities ALTER COLUMN date TYPE timestamptz USING date AT TIME ZONE 'UTC'"
    )


def downgrade():
    op.execute(
        "ALTER TABLE activities ALTER COLUMN date TYPE timestamp USING date AT TIME ZONE 'UTC'"
    )
    op.drop_column("users", "timezone")
