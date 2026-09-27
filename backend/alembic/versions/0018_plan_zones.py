"""Zones/plan format: user HR+pace inputs, activity effort, workout source/rpe, plan_preferences

Revision ID: 0018_plan_zones
Revises: 0017_untracked_schema
Create Date: 2026-09-24

Только добавляющие изменения (nullable-колонки и новая таблица) — старые планы и
пользователи продолжают работать без пересчёта.
"""
import sqlalchemy as sa
from alembic import op

revision = '0018_plan_zones'
down_revision = '0017_untracked_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('max_hr', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('rest_hr', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('easy_pace_min_km', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('race_distance_km', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('race_time_min', sa.Float(), nullable=True))

    op.add_column('activities', sa.Column('effort', sa.String(10), nullable=True))

    op.add_column('workouts', sa.Column('plan_source', sa.String(10), nullable=True))
    op.add_column('workouts', sa.Column('rpe', sa.String(10), nullable=True))

    op.create_table(
        'plan_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('training_days', sa.Integer(), nullable=True),
        sa.Column('long_run_day', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index('ix_plan_preferences_id', 'plan_preferences', ['id'])
    op.create_index('ix_plan_preferences_user_id', 'plan_preferences', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_plan_preferences_user_id', table_name='plan_preferences')
    op.drop_index('ix_plan_preferences_id', table_name='plan_preferences')
    op.drop_table('plan_preferences')
    op.drop_column('workouts', 'rpe')
    op.drop_column('workouts', 'plan_source')
    op.drop_column('activities', 'effort')
    op.drop_column('users', 'race_time_min')
    op.drop_column('users', 'race_distance_km')
    op.drop_column('users', 'easy_pace_min_km')
    op.drop_column('users', 'rest_hr')
    op.drop_column('users', 'max_hr')
