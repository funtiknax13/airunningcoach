"""add indexes on hot-path user_id columns

Без этих индексов запросы «активности/чат/цели пользователя» делали sequential
scan всей таблицы — медленно и тем хуже, чем больше данных. Добавляем индексы
на user_id (+ композитные с date/created_at под фактические сортировки).

Revision ID: 0007_hot_path_indexes
Revises: 0006_payments
Create Date: 2026-06-18 00:00:00
"""
from alembic import op


revision = "0007_hot_path_indexes"
down_revision = "0006_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_activities_user_date", "activities", ["user_id", "date"])
    op.create_index("ix_chat_messages_user_created", "chat_messages", ["user_id", "created_at"])
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"])
    op.create_index("ix_workouts_training_plan_id", "workouts", ["training_plan_id"])


def downgrade():
    op.drop_index("ix_workouts_training_plan_id", table_name="workouts")
    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    op.drop_index("ix_goals_user_id", table_name="goals")
    op.drop_index("ix_chat_messages_user_created", table_name="chat_messages")
    op.drop_index("ix_activities_user_date", table_name="activities")
