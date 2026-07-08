# app/services/workout_verification.py
"""Сопоставление плановой тренировки с реально залогированной пробежкой.

Допуск — относительный (% от плановой цели), а не абсолютный: план на 5 км
и план на 30 км должны прощать разное абсолютное отклонение.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Activity, Workout

DEVIATION_OK      = 0.07  # ≤7%  — план выполнен чисто
DEVIATION_PARTIAL = 0.30  # 7-30% — частично (слишком быстро/медленно/не туда); >30% — не подтверждено

STATUS_LABELS = {
    "none":        "Не начата",
    "completed":   "Выполнена",
    "approximate": "Частично выполнена",
    "unconfirmed": "Не подтверждена",
}


def _deviation(actual: float | None, target: float | None) -> float:
    """Относительное отклонение факта от плана. Нет цели — отклонения нет."""
    if not target:
        return 0.0
    if actual is None:
        return 1.0  # цель была, факта нет — максимальное расхождение
    return abs(actual - target) / target


def verdict_for(activity: Activity | None, workout: Workout) -> str:
    """completion_status по факту относительно плана этой тренировки."""
    if activity is None:
        return "unconfirmed"
    worst = max(
        _deviation(activity.distance_km, workout.distance_km),
        _deviation(activity.pace_min_per_km, workout.target_pace_min_km),
    )
    if worst <= DEVIATION_OK:
        return "completed"
    if worst <= DEVIATION_PARTIAL:
        return "approximate"
    return "unconfirmed"


def find_matching_workout_for_activity(activity: Activity, user_id: int, db: Session) -> Workout | None:
    """Активность → тренировка пользователя на ту же дату (тип rest не считается)."""
    act_date = activity.date.date() if hasattr(activity.date, 'date') else activity.date
    day_start = datetime.combine(act_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    workout = (
        db.query(Workout)
        .filter(
            Workout.user_id == user_id,
            Workout.planned_date >= day_start,
            Workout.planned_date < day_end,
        )
        .first()
    )

    if not workout:
        workout = (
            db.query(Workout)
            .filter(
                Workout.user_id == user_id,
                Workout.planned_date.is_(None),
                Workout.day_of_week == activity.date.weekday(),
            )
            .first()
        )

    if not workout or workout.workout_type == "rest":
        return None
    return workout


def find_matching_activity_for_workout(workout: Workout, user_id: int, db: Session) -> Activity | None:
    """Тренировка → лучшая (ближе всего к плану) пробежка в пределах ±1 дня от planned_date."""
    if not workout.planned_date:
        return None

    window_start = workout.planned_date - timedelta(days=1)
    window_end = workout.planned_date + timedelta(days=1)
    candidates = (
        db.query(Activity)
        .filter(
            Activity.user_id == user_id,
            Activity.activity_type == "run",
            Activity.date >= window_start,
            Activity.date <= window_end,
        )
        .all()
    )
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda a: (
            _deviation(a.distance_km, workout.distance_km)
            + _deviation(a.pace_min_per_km, workout.target_pace_min_km)
        ),
    )


def apply_verdict(workout: Workout, activity: Activity | None) -> None:
    """Проставляет completion_status/completed/activity_id на тренировке по вердикту."""
    status = verdict_for(activity, workout)
    workout.completion_status = status
    workout.completed = status in ("completed", "approximate")
    workout.activity_id = activity.id if activity else None
