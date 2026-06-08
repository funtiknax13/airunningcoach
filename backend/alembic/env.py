# alembic/env.py
import os
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Импортируем Base и модели
from app.database import Base
from app.models import User, Activity, Goal, TrainingPlan, Workout, ChatMessage, InsightsCache, ApiUsage

# Получаем конфигурацию Alembic
config = context.config

# Настройка логирования (если файл существует)
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except:
        pass

# ── Подставляем DATABASE_URL из переменной окружения / settings ──
from app.core.config import settings
# Перезаписываем sqlalchemy.url — игнорируем alembic.ini
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Метаданные для autogenerate
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    from sqlalchemy import create_engine
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()