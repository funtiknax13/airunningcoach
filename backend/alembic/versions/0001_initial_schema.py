"""Initial schema (PostgreSQL)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',                          sa.Integer(),               nullable=False),
        sa.Column('email',                        sa.String(255),             nullable=False),
        sa.Column('password_hash',                sa.String(255),             nullable=False),
        sa.Column('name',                         sa.String(100),             nullable=False),
        sa.Column('age',                          sa.Integer(),               nullable=True),
        sa.Column('weight',                       sa.Float(),                 nullable=True),
        sa.Column('height',                       sa.Float(),                 nullable=True),
        sa.Column('is_verified',                  sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('is_admin',                     sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('verification_token',           sa.String(64),              nullable=True),
        sa.Column('verification_token_expires',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_token',                  sa.String(64),              nullable=True),
        sa.Column('reset_token_expires',          sa.DateTime(timezone=True), nullable=True),
        sa.Column('google_id',                    sa.String(128),             nullable=True),
        sa.Column('created_at',                   sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',                   sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id', name='uq_users_google_id'),
    )
    op.create_index('ix_users_id',                 'users', ['id'])
    op.create_index('ix_users_email',              'users', ['email'])
    op.create_index('ix_users_verification_token', 'users', ['verification_token'])
    op.create_index('ix_users_reset_token',        'users', ['reset_token'])
    op.create_index('ix_users_google_id',          'users', ['google_id'])

    # ── activities ─────────────────────────────────────────────────────────────
    op.create_table(
        'activities',
        sa.Column('id',               sa.Integer(),               nullable=False),
        sa.Column('user_id',          sa.Integer(),               nullable=False),
        sa.Column('date',             sa.DateTime(),              nullable=False),
        sa.Column('distance_km',      sa.Float(),                 nullable=False),
        sa.Column('duration_min',     sa.Float(),                 nullable=False),
        sa.Column('pace_min_per_km',  sa.Float(),                 nullable=True),
        sa.Column('avg_heart_rate',   sa.Integer(),               nullable=True),
        sa.Column('calories',         sa.Integer(),               nullable=True),
        sa.Column('notes',            sa.Text(),                  nullable=True),
        sa.Column('source',           sa.String(50),              nullable=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activities_id', 'activities', ['id'])

    # ── goals ──────────────────────────────────────────────────────────────────
    op.create_table(
        'goals',
        sa.Column('id',                  sa.Integer(),               nullable=False),
        sa.Column('user_id',             sa.Integer(),               nullable=False),
        sa.Column('goal_type',           sa.String(50),              nullable=False),
        sa.Column('target_distance_km',  sa.Float(),                 nullable=True),
        sa.Column('target_time_min',     sa.Float(),                 nullable=True),
        sa.Column('target_date',         sa.DateTime(),              nullable=True),
        sa.Column('description',         sa.Text(),                  nullable=True),
        sa.Column('is_active',           sa.Boolean(),               nullable=True,  server_default='true'),
        sa.Column('is_achieved',         sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('is_abandoned',        sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('created_at',          sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at',          sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goals_id', 'goals', ['id'])

    # ── training_plans ─────────────────────────────────────────────────────────
    op.create_table(
        'training_plans',
        sa.Column('id',              sa.Integer(),               nullable=False),
        sa.Column('user_id',         sa.Integer(),               nullable=False),
        sa.Column('week_start_date', sa.DateTime(),              nullable=False),
        sa.Column('week_end_date',   sa.DateTime(),              nullable=False),
        sa.Column('goal_type',       sa.String(50),              nullable=True),
        sa.Column('is_active',       sa.Boolean(),               nullable=True, server_default='true'),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_training_plans_id', 'training_plans', ['id'])

    # ── workouts ───────────────────────────────────────────────────────────────
    op.create_table(
        'workouts',
        sa.Column('id',                 sa.Integer(),  nullable=False),
        sa.Column('training_plan_id',   sa.Integer(),  nullable=False),
        sa.Column('day_of_week',        sa.Integer(),  nullable=False),
        sa.Column('workout_type',       sa.String(50), nullable=False),
        sa.Column('description',        sa.Text(),     nullable=False),
        sa.Column('distance_km',        sa.Float(),    nullable=True),
        sa.Column('target_pace_min_km', sa.Float(),    nullable=True),
        sa.Column('duration_min',       sa.Float(),    nullable=True),
        sa.Column('planned_date',       sa.DateTime(), nullable=True),
        sa.Column('completed',          sa.Boolean(),  nullable=True, server_default='false'),
        sa.Column('completion_status',  sa.String(20), nullable=True, server_default='none'),
        sa.Column('notes_after',        sa.Text(),     nullable=True),
        sa.ForeignKeyConstraint(['training_plan_id'], ['training_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workouts_id', 'workouts', ['id'])

    # ── chat_messages ──────────────────────────────────────────────────────────
    op.create_table(
        'chat_messages',
        sa.Column('id',           sa.Integer(),               nullable=False),
        sa.Column('user_id',      sa.Integer(),               nullable=False),
        sa.Column('role',         sa.String(20),              nullable=False),
        sa.Column('content',      sa.Text(),                  nullable=False),
        sa.Column('context_type', sa.String(50),              nullable=True),
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_id', 'chat_messages', ['id'])

    # ── insights_cache ─────────────────────────────────────────────────────────
    op.create_table(
        'insights_cache',
        sa.Column('id',         sa.Integer(),               nullable=False),
        sa.Column('user_id',    sa.Integer(),               nullable=False),
        sa.Column('payload',    sa.Text(),                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_insights_cache_id',      'insights_cache', ['id'])
    op.create_index('ix_insights_cache_user_id', 'insights_cache', ['user_id'])


def downgrade() -> None:
    op.drop_table('insights_cache')
    op.drop_table('chat_messages')
    op.drop_table('workouts')
    op.drop_table('training_plans')
    op.drop_table('goals')
    op.drop_table('activities')
    op.drop_table('users')
