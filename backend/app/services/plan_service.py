"""Слой между БД и чистой логикой плана (зоны, формат отрезков, планировщик).

- собирает PlanRequest из профиля, истории пробежек, целей, пожеланий из чата;
- пересчитывает числа в будущих тренировках при изменении зон (самокалибровка);
- возвращает пользователю его зоны и статус «нужны ли данные».
Чистая логика (без БД) живёт в zones.py / plan_format.py / planner.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Activity, Goal, Workout
from app.services import chat_prefs, plan_format as pf, planner
from app.services.zones import Zones, build_zones, data_status

logger = logging.getLogger(__name__)

HISTORY_LOAD_WEEKS = 12
DONE = ("completed", "approximate")


def load_activities(db: Session, user_id: int, now: datetime | None = None) -> list[Activity]:
    now = now or datetime.now(timezone.utc)
    return (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.date >= now - timedelta(weeks=HISTORY_LOAD_WEEKS))
        .order_by(Activity.date.desc())
        .limit(300)
        .all()
    )


def zones_for_user(user, db: Session, now: datetime | None = None) -> tuple[Zones, list[Activity]]:
    activities = load_activities(db, user.id, now)
    return build_zones(user, activities, now), activities


def zones_payload(user, db: Session, now: datetime | None = None) -> dict:
    """Ответ GET /training/zones: зоны + статус данных для окна «Нужны данные»."""
    zones, activities = zones_for_user(user, db, now)
    pref = chat_prefs.get_pref(db, user.id)
    return {
        "zones": zones.to_dict(),
        "data_status": data_status(zones, activities, now),
        "training_days": chat_prefs.effective_training_days(user, pref),
    }


def _completed_beginner_sessions(db: Session, user_id: int) -> int:
    rows = (
        db.query(Workout)
        .filter(Workout.user_id == user_id, Workout.completion_status.in_(DONE))
        .order_by(Workout.planned_date.desc())
        .limit(120)
        .all()
    )
    count = 0
    for w in rows:
        ps = w.plan_structure
        if isinstance(ps, dict) and ps.get("version") == pf.VERSION:
            segs = ps.get("segments") or []
            if segs and segs[0].get("kind") == "walk":
                count += 1
    return count


def _recent_rpe(db: Session, user_id: int, n: int = 3) -> list[str]:
    rows = (
        db.query(Workout.rpe)
        .filter(Workout.user_id == user_id, Workout.rpe.isnot(None))
        .order_by(Workout.planned_date.desc())
        .limit(n)
        .all()
    )
    return [r[0] for r in reversed(rows)]


def build_request(user, db: Session, start: datetime, days: int,
                  now: datetime | None = None) -> planner.PlanRequest:
    """Собирает всё, что нужно планировщику и проверке плана ИИ (один проход по БД)."""
    now = now or datetime.now(timezone.utc)
    zones, activities = zones_for_user(user, db, now)
    stats = planner.history_stats(activities, now)
    pref = chat_prefs.get_pref(db, user.id)
    goal = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.is_active == True, Goal.target_date.isnot(None))  # noqa: E712
        .order_by(Goal.target_date.asc())
        .first()
    )
    goal_date = goal.target_date.date() if goal and goal.target_date else None
    if goal_date and goal_date < start.date():
        goal_date = None
    return planner.PlanRequest(
        start=start, days=days, zones=zones,
        training_days=chat_prefs.effective_training_days(user, pref),
        long_run_day=chat_prefs.effective_long_run_day(pref),
        level=user.fitness_level, goal=user.running_goal,
        weekly_km_profile=user.weekly_km,
        history_avg_km=stats["avg_km"], history_runs_4w=stats["runs_4w"],
        longest_run_km=stats["longest_km"], goal_date=goal_date,
        completed_beginner_sessions=_completed_beginner_sessions(db, user.id),
        recent_rpe=_recent_rpe(db, user.id),
    )


def refresh_workout(workout: Workout, zones: Zones) -> bool:
    """Пересчитывает числа одной тренировки v2 по зонам. False — структура не v2."""
    res = pf.refresh_structure(workout.plan_structure, zones)
    if res is None:
        return False
    structure, fields = res
    workout.plan_structure = structure           # присваиваем новый dict — SQLAlchemy заметит изменение
    workout.distance_km = fields["distance_km"]
    workout.duration_min = fields["duration_min"]
    workout.target_pace_min_km = fields["target_pace_min_km"]
    return True


def refresh_future_workouts(user, db: Session, now: datetime | None = None) -> int:
    """Пересчитывает числа (темп, пульс, средний темп, дистанция при времени) в будущих
    невыполненных тренировках v2 по актуальным зонам. Выполненные не трогаем — они
    хранят числа на момент выполнения. Не коммитит. Возвращает число обновлённых."""
    now = now or datetime.now(timezone.utc)
    zones, _ = zones_for_user(user, db, now)
    today = datetime.now().date()
    rows = (
        db.query(Workout)
        .filter(Workout.user_id == user.id, Workout.planned_date >= datetime.combine(today, datetime.min.time()),
                Workout.completion_status == "none")
        .all()
    )
    return sum(1 for w in rows if refresh_workout(w, zones))


def refresh_after_change(user, db: Session) -> None:
    """Безопасная обёртка для роутеров: сбой пересчёта не должен ломать сохранение
    пробежки или профиля."""
    try:
        if refresh_future_workouts(user, db):
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("refresh_future_workouts failed (user %s)", getattr(user, "id", "?"))
