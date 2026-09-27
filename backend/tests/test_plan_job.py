import asyncio
from datetime import datetime

import pytest

from app.models import ApiUsage, PlanJob, User, Workout
from app.services import ai_agent


class _SessionFactory:
    """SessionLocal-замена: отдаёт одну и ту же тестовую сессию (закрытие допустимо)."""
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


def _user(db, **kw):
    base = dict(email="j@example.com", password_hash="x", name="J", is_verified=True,
                fitness_level="intermediate", running_goal="10k", weekly_km=20.0,
                training_days=4, timezone="UTC", easy_pace_min_km=7.5)
    base.update(kw)
    u = User(**base)
    db.add(u)
    db.commit()
    return u


def test_month_job_builds_28_days_by_rules_without_ai_and_refunds(db, monkeypatch):
    monkeypatch.setattr(ai_agent, "SessionLocal", _SessionFactory(db))
    user = _user(db)
    db.add(ApiUsage(user_id=user.id, action="plan"))
    job = PlanJob(user_id=user.id, weeks=4, status="running")
    db.add(job)
    db.commit()

    asyncio.run(ai_agent.run_plan_job(user.id, 4, job.id))

    assert db.get(PlanJob, job.id).status == "done"
    workouts = db.query(Workout).filter(Workout.user_id == user.id).all()
    assert len(workouts) == 28
    assert {w.plan_source for w in workouts} == {"rules"}      # целиком по правилам, без смеси
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 0
    # каждая календарная неделя — не больше 4 тренировочных дней
    from collections import Counter
    weeks = Counter()
    for w in workouts:
        if w.workout_type != "rest":
            weeks[w.planned_date.date().isocalendar()[:2]] += 1
    assert max(weeks.values()) <= 4


def test_month_job_marks_failed_on_unexpected_error(db, monkeypatch):
    monkeypatch.setattr(ai_agent, "SessionLocal", _SessionFactory(db))
    user = _user(db)
    job = PlanJob(user_id=user.id, weeks=4, status="running")
    db.add(job)
    db.commit()

    async def boom(*a, **k):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(ai_agent.plan_ai, "generate", boom)
    asyncio.run(ai_agent.run_plan_job(user.id, 4, job.id))
    done = db.get(PlanJob, job.id)
    assert done.status == "failed" and "exploded" in done.error
    assert db.query(Workout).filter(Workout.user_id == user.id).count() == 0     # старый план не тронут


def test_replace_upcoming_workouts_keeps_completed_days_and_ignores_empty(db):
    user = _user(db)
    start = datetime(2026, 9, 28)
    done = Workout(user_id=user.id, day_of_week=0, planned_date=start, workout_type="easy",
                   description="x", completion_status="completed", completed=True)
    db.add(done)
    db.commit()
    ai_agent.replace_upcoming_workouts(user.id, db, [], start)         # пусто -> ничего не стираем
    assert db.query(Workout).count() == 1
    days = [{"workout_type": "easy", "description": "new", "distance_km": 5, "plan_source": "ai"}] * 7
    ai_agent.replace_upcoming_workouts(user.id, db, days, start)
    db.commit()
    rows = db.query(Workout).order_by(Workout.planned_date).all()
    assert rows[0].completion_status == "completed" and rows[0].description == "x"   # выполненный сохранён
    assert all(r.plan_source == "ai" for r in rows[1:])
