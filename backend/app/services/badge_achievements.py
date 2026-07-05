# app/services/badge_achievements.py
"""Разблокировка «достижений» (бейджей) — односторонний храповик: только
добавляет новые заработанные достижения, никогда не отзывает уже полученные.

earned_at всегда ставится по дате пробежки/события, которое реально закрыло
условие — не по дате запуска пересчёта. Это важно для бэкафилла: у давно
зарегистрированных пользователей достижения "задним числом" получают дату,
когда они были фактически заслужены, а не сегодняшнюю.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Activity, Goal, TrainingPlan, UserAchievement, Workout
from app.services.achievement_defs import ACHIEVEMENT_DEFS


def _to_dt(value) -> datetime | None:
    """Приводит date/datetime к datetime (полночь для чистой date)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())


def _week_start(value):
    d = value.date() if hasattr(value, "date") else value
    return d - timedelta(days=d.weekday())


def _longest_consecutive_week_run(week_starts: set) -> int:
    """Длина самой длинной последовательности подряд идущих недель (шаг ровно 7 дней)."""
    if not week_starts:
        return 0
    weeks_sorted = sorted(week_starts)
    best = cur = 1
    for prev, nxt in zip(weeks_sorted, weeks_sorted[1:]):
        cur = cur + 1 if (nxt - prev).days == 7 else 1
        best = max(best, cur)
    return best


def _streak_completion_date(week_starts: set, weeks_needed: int) -> datetime | None:
    """Дата (воскресенье завершающей недели), когда впервые набралась
    непрерывная последовательность из weeks_needed недель подряд."""
    weeks_sorted = sorted(week_starts)
    run_len = 0
    prev = None
    for wk in weeks_sorted:
        run_len = run_len + 1 if prev is not None and (wk - prev).days == 7 else 1
        prev = wk
        if run_len >= weeks_needed:
            return _to_dt(wk + timedelta(days=6))
    return None


def _first_match_date(activities: list[Activity], predicate) -> datetime | None:
    for a in activities:
        if a.date and predicate(a):
            return a.date
    return None


def _first_crossing_date(activities: list[Activity], value_fn, threshold: float) -> datetime | None:
    """Дата активности, на которой накопленная (по value_fn) сумма впервые достигла threshold."""
    total = 0.0
    for a in activities:
        total += value_fn(a) or 0.0
        if total >= threshold:
            return a.date
    return None


def _monthly_crossing_date(activities: list[Activity], threshold: float) -> datetime | None:
    """Дата активности, на которой сумма км за ЕЁ календарный месяц впервые достигла threshold."""
    running: dict[tuple, float] = defaultdict(float)
    for a in activities:
        if not a.date or not a.distance_km:
            continue
        key = (a.date.year, a.date.month)
        running[key] += a.distance_km
        if running[key] >= threshold:
            return a.date
    return None


def _collect_run_stats(user_id: int, db: Session) -> dict:
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.activity_type == "run")
        .order_by(Activity.date)
        .all()
    )

    weekly_counts: dict = defaultdict(int)  # week_start (date, monday) -> кол-во пробежек
    for a in activities:
        if a.date:
            weekly_counts[_week_start(a.date)] += 1

    return {"activities": activities, "weekly_counts": weekly_counts}


def _collect_plan_stats(user_id: int, db: Session) -> dict:
    plans = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id)
        .order_by(TrainingPlan.week_start_date)
        .all()
    )
    workouts_by_plan = defaultdict(list)
    if plans:
        for w in db.query(Workout).filter(Workout.training_plan_id.in_([p.id for p in plans])).all():
            workouts_by_plan[w.training_plan_id].append(w)

    perfect_week_date = None
    clean_weeks = set()
    variety_events: list[tuple[datetime, str]] = []  # (дата, workout_type) для completed/approximate

    for p in plans:
        ws = workouts_by_plan.get(p.id, [])
        non_rest = [w for w in ws if w.workout_type != "rest"]
        if non_rest and all(w.completion_status == "completed" for w in non_rest) and perfect_week_date is None:
            perfect_week_date = p.week_end_date or p.week_start_date
        if non_rest and all(w.completion_status != "unconfirmed" for w in non_rest):
            clean_weeks.add(_week_start(p.week_start_date))
        for w in ws:
            if w.completion_status in ("completed", "approximate"):
                w_date = (w.activity.date if w.activity and w.activity.date else w.planned_date) or p.week_start_date
                variety_events.append((w_date, w.workout_type))

    variety_events.sort(key=lambda x: x[0])

    goals_achieved = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.is_achieved == True)
        .order_by(Goal.updated_at.asc())
        .all()
    )

    return {
        "perfect_week_date": perfect_week_date,
        "clean_weeks": clean_weeks,
        "variety_events": variety_events,
        "goals_achieved": goals_achieved,
    }


def _evaluate(d: dict, stats: dict, plan_stats: dict) -> datetime | None:
    """Возвращает дату, когда достижение было заслужено, либо None, если ещё не заслужено."""
    t = d["type"]
    activities = stats["activities"]

    if t == "count":
        n = d["value"]
        return activities[n - 1].date if len(activities) >= n else None

    if t == "distance":
        # Дистанцию нужно пробежать (можно больше — без потолка), но допускаем
        # погрешность GPS-трека в 0.5% в меньшую сторону, иначе честный полумарафон
        # на 21.0км (а не ровно 21.0975) не засчитался бы.
        threshold = d["value"] * 0.995
        return _first_match_date(activities, lambda a: (a.distance_km or 0) >= threshold)

    if t == "total_distance":
        return _first_crossing_date(activities, lambda a: a.distance_km, d["value"])

    if t == "monthly_volume":
        return _monthly_crossing_date(activities, d["value"])

    if t == "elevation":
        return _first_match_date(activities, lambda a: (a.elevation_gain or 0) >= d["value"])

    if t == "elevation_total":
        return _first_crossing_date(activities, lambda a: a.elevation_gain, d["value"])

    if t == "streak":
        min_per_week = d.get("min_per_week", 3)
        qualifying = {wk for wk, cnt in stats["weekly_counts"].items() if cnt >= min_per_week}
        return _streak_completion_date(qualifying, d["weeks"])

    if t == "pace":
        target_km = d["distance_km"]
        required_pace = d["max_time_min"] / target_km
        return _first_match_date(
            activities,
            lambda a: a.distance_km and a.pace_min_per_km
            and a.distance_km >= target_km * 0.95
            and a.pace_min_per_km <= required_pace,
        )

    if t == "comeback":
        gap_days = d.get("gap_days", 30)
        for a, b in zip(activities, activities[1:]):
            if a.date and b.date and (b.date - a.date).days >= gap_days:
                return b.date
        return None

    if t == "time_of_day":
        if "before_hour" in d:
            return _first_match_date(activities, lambda a: a.date.hour < d["before_hour"])
        if "after_hour" in d:
            return _first_match_date(activities, lambda a: a.date.hour >= d["after_hour"])
        return None

    if t == "plan_adherence":
        if d.get("mode") == "perfect_week":
            return _to_dt(plan_stats["perfect_week_date"])
        if d.get("mode") == "discipline":
            return _streak_completion_date(plan_stats["clean_weeks"], d.get("weeks", 4))
        return None

    if t == "goal":
        goals = plan_stats["goals_achieved"]
        if not goals:
            return None
        first = goals[0]
        return _to_dt(first.updated_at or first.created_at)

    if t == "variety":
        min_types = d.get("min_types", 4)
        seen = set()
        for event_date, wtype in plan_stats["variety_events"]:
            seen.add(wtype)
            if len(seen) >= min_types:
                return _to_dt(event_date)
        return None

    return None


def recompute_badge_achievements(user_id: int, db: Session) -> None:
    already_rows = db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
    already = {ua.achievement_key for ua in already_rows}
    earned_at_by_key = {ua.achievement_key: ua.earned_at for ua in already_rows}

    remaining = [d for d in ACHIEVEMENT_DEFS if d["key"] not in already]
    if not remaining:
        return

    stats = _collect_run_stats(user_id, db)
    plan_stats = _collect_plan_stats(user_id, db)

    newly_earned: dict[str, datetime] = {}
    for d in remaining:
        if d["type"] == "meta":
            continue  # мета-достижение оценивается последним, после всех остальных
        earned_at = _evaluate(d, stats, plan_stats)
        if earned_at is not None:
            newly_earned[d["key"]] = earned_at

    unlocked_after = already | newly_earned.keys()
    for d in remaining:
        if d["type"] != "meta":
            continue
        required = {k for k in (x["key"] for x in ACHIEVEMENT_DEFS) if k not in d.get("exclude", []) and k != d["key"]}
        if required <= unlocked_after:
            dates = [earned_at_by_key.get(k) or newly_earned.get(k) for k in required]
            dates = [dt for dt in dates if dt is not None]
            newly_earned[d["key"]] = max(dates) if dates else datetime.now()

    for key, earned_at in newly_earned.items():
        db.add(UserAchievement(user_id=user_id, achievement_key=key, earned_at=earned_at))
    db.commit()
