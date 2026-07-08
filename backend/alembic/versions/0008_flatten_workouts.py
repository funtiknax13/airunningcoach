"""flatten workouts: drop training_plans, workouts get user_id directly

Тренировки больше не группируются в недельные "планы". Раньше перегенерация
плана деактивировала весь план целиком, и уже выполненные тренировки текущей
недели оставались висеть в неактивном плане — невидимые для пользователя,
хотя формально не удалялись. Теперь Workout — самостоятельная запись с
planned_date как единственным якорем и user_id напрямую, без плана-контейнера.

Revision ID: 0008_flatten_workouts
Revises: 0007_hot_path_indexes
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_flatten_workouts"
down_revision = "0007_hot_path_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workouts", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE workouts SET user_id = "
        "(SELECT user_id FROM training_plans WHERE training_plans.id = workouts.training_plan_id)"
    )

    with op.batch_alter_table("workouts") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("fk_workouts_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")

    op.create_index("ix_workouts_user_id", "workouts", ["user_id"])
    op.drop_index("ix_workouts_training_plan_id", table_name="workouts")

    with op.batch_alter_table("workouts") as batch_op:
        batch_op.drop_column("training_plan_id")

    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    op.drop_index("ix_training_plans_id", table_name="training_plans")
    op.drop_table("training_plans")


def downgrade():
    op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.DateTime(), nullable=False),
        sa.Column("week_end_date", sa.DateTime(), nullable=False),
        sa.Column("goal_type", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_plans_id", "training_plans", ["id"])
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"])

    op.add_column("workouts", sa.Column("training_plan_id", sa.Integer(), nullable=True))
    op.create_index("ix_workouts_training_plan_id", "workouts", ["training_plan_id"])

    with op.batch_alter_table("workouts") as batch_op:
        batch_op.drop_constraint("fk_workouts_user_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            "workouts_training_plan_id_fkey", "training_plans", ["training_plan_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.drop_index("ix_workouts_user_id")
        batch_op.drop_column("user_id")
    # training_plans восстанавливается пустой таблицей — привязка тренировок к
    # недельным планам необратимо теряется, это осознанный компромисс downgrade
