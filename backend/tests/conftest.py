import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# Тесты не должны видеть боевой .env: подменяем ДО импорта приложения.
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")

import pytest  # noqa: E402

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def now():
    return NOW


def make_run(days_ago: float, distance_km: float, pace: float, *, effort=None,
             max_hr=None, activity_type="run", now=NOW):
    """Лёгкая «активность» без БД (duck typing под app.models.Activity)."""
    return SimpleNamespace(
        date=now - timedelta(days=days_ago), distance_km=distance_km,
        duration_min=distance_km * pace, pace_min_per_km=pace, effort=effort,
        max_heart_rate=max_hr, activity_type=activity_type,
    )


def make_user(**kw):
    base = dict(id=1, age=None, weight=None, height=None, gender=None,
                fitness_level="intermediate", running_goal="10k", weekly_km=20.0,
                training_days=4, max_hr=None, rest_hr=None, easy_pace_min_km=None,
                race_distance_km=None, race_time_min=None, timezone="UTC")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def db():
    """Чистая in-memory SQLite-БД на каждый тест (боевая логика с PG-локами не задействована)."""
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    import app.models  # noqa: F401  (регистрирует таблицы)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
