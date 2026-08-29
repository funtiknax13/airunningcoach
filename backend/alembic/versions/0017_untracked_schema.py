"""Bring personal_records/push_subscriptions and several columns under alembic

Revision ID: 0017_untracked_schema
Revises: 0016_analytics_columns
Create Date: 2026-08-29

These have existed on prod for a long time but were never created/altered by
any alembic migration — only by Base.metadata.create_all() (tables) and a
parallel hand-rolled _migrate() function in main.py (columns + FK ON DELETE).
That meant `alembic upgrade head` alone could never reproduce the real schema
on a fresh database (0010_read_seen tried to ALTER a table that no migration
had created — see the defensive fix added there). This migration is written
to be a safe no-op on prod (everything already exists there) while making a
from-scratch `alembic upgrade head` actually work. main.py's create_all()/
_migrate()/_fk_ondelete_sql() are removed in the same change — this migration
is now the only place that creates/alters this schema.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0017_untracked_schema"
down_revision = "0016_analytics_columns"
branch_labels = None
depends_on = None


def _fk_ondelete(table: str, column: str, on_delete: str) -> None:
    """Находит текущее имя FK-constraint'а на table.column (может быть создан
    Base.metadata.create_all с дефолтным именем, без ON DELETE) и пересоздаёт
    с нужным ON DELETE. Идемпотентно — пересоздание с тем же ON DELETE безвредно."""
    op.execute(f"""
    DO $$
    DECLARE r RECORD;
    BEGIN
        FOR r IN
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = '{table}'
              AND kcu.column_name = '{column}'
        LOOP
            EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', r.constraint_name);
        END LOOP;
        EXECUTE 'ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_fkey FOREIGN KEY ({column}) REFERENCES activities(id) ON DELETE {on_delete}';
    END $$;
    """)


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing = inspector.get_table_names()

    if "personal_records" not in existing:
        op.create_table(
            "personal_records",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("distance_key", sa.String(30), nullable=False),
            sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id"), nullable=False),
            sa.Column("distance_km", sa.Float(), nullable=True),
            sa.Column("time_sec", sa.Float(), nullable=False),
            sa.Column("achieved_rank", sa.String(10), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_pr_user_distance", "personal_records", ["user_id", "distance_key"], unique=True)
    else:
        op.execute("ALTER TABLE personal_records ADD COLUMN IF NOT EXISTS distance_km FLOAT")

    if "push_subscriptions" not in existing:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
            sa.Column("p256dh", sa.String(255), nullable=False),
            sa.Column("auth", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # Раньше — main.py:_migrate(), идемпотентно вне alembic. Теперь здесь.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS fitness_level VARCHAR(20)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS running_goal VARCHAR(20)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_km FLOAT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS training_days INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(10)")
    op.execute("ALTER TABLE workouts ADD COLUMN IF NOT EXISTS activity_id INTEGER REFERENCES activities(id)")

    # activity_id FK-и изначально создавались (через create_all) без ON DELETE —
    # удаление пробежки, на которую ссылается тренировка/рекорд/достижение, падало
    # с ForeignKeyViolation. SET NULL (история сохраняется) / CASCADE (рекорд
    # пересчитывается в recompute_achievements сразу после удаления).
    _fk_ondelete("workouts", "activity_id", "SET NULL")
    _fk_ondelete("personal_records", "activity_id", "CASCADE")
    _fk_ondelete("user_achievements", "activity_id", "SET NULL")


def downgrade() -> None:
    # Одностороннее — эти таблицы/колонки годами существовали вне alembic,
    # откатывать их удалением рискованнее, чем оставить (реальных данных лишиться
    # можно, а привести схему в состояние "как будто миграции не было" всё равно
    # нельзя, раз create_all её создавал независимо от alembic).
    pass
