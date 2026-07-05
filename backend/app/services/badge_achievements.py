# app/services/badge_achievements.py
"""Разблокировка «достижений» (бейджей) — односторонний храповик: только
добавляет новые заработанные достижения, никогда не отзывает уже полученные."""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Activity, Goal, TrainingPlan, UserAchievement, Workout
from app.services.achievement_defs import ACHIEVEMENT_DEFS


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


def _collect_run_stats(user_id: int, db: Session) -> dict:
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.activity_type == "run")
        .order_by(Activity.date)
        .all()
    )

    monthly_totals: dict[tuple, float] = defaultdict(float)
    weekly_counts: dict = defaultdict(int)  # week_start (date, monday) -> кол-во пробежек

    for a in activities:
        if not a.date:
            continue
        d = a.date.date() if hasattr(a.date, 'date') else a.date
        if a.distance_km:
            monthly_totals[(d.year, d.month)] += a.distance_km
        week_start = d - timedelta(days=d.weekday())
        weekly_counts[week_start] += 1

    return {
        "activities": activities,
        "total_count": len(activities),
        "max_distance": max((a.distance_km or 0 for a in activities), default=0),
        "total_distance": sum(a.distance_km or 0 for a in activities),
        "max_elevation": max((a.elevation_gain or 0 for a in activities), default=0),
        "total_elevation": sum(a.elevation_gain or 0 for a in activities),
        "best_month": max(monthly_totals.values(), default=0),
        "weekly_counts": weekly_counts,
    }


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

    perfect_week = False
    clean_weeks = set()
    workout_types_completed = set()

    for p in plans:
        ws = workouts_by_plan.get(p.id, [])
        non_rest = [w for w in ws if w.workout_type != "rest"]
        if non_rest and all(w.completion_status == "completed" for w in non_rest):
            perfect_week = True
        if non_rest and all(w.completion_status != "unconfirmed" for w in non_rest):
            wsd = p.week_start_date.date() if hasattr(p.week_start_date, 'date') else p.week_start_date
            clean_weeks.add(wsd)
        for w in ws:
            if w.completion_status in ("completed", "approximate"):
                workout_types_completed.add(w.workout_type)

    goal_achieved = (
        db.query(Goal).filter(Goal.user_id == user_id, Goal.is_achieved == True).first() is not None
    )

    return {
        "perfect_week": perfect_week,
        "clean_week_streak": _longest_consecutive_week_run(clean_weeks),
        "workout_type_variety": len(workout_types_completed),
        "goal_achieved": goal_achieved,
    }


def _check(d: dict, stats: dict, plan_stats: dict) -> bool:
    t = d["type"]

    if t == "count":
        return stats["total_count"] >= d["value"]
    if t == "distance":
        # Дистанцию нужно пробежать (можно больше — без потолка), но допускаем
        # погрешность GPS-трека в 0.5% в меньшую сторону, иначе честный полумарафон
        # на 21.0км (а не ровно 21.0975) не засчитался бы.
        return stats["max_distance"] >= d["value"] * 0.995
    if t == "total_distance":
        return stats["total_distance"] >= d["value"]
    if t == "monthly_volume":
        return stats["best_month"] >= d["value"]
    if t == "elevation":
        return stats["max_elevation"] >= d["value"]
    if t == "elevation_total":
        return stats["total_elevation"] >= d["value"]

    if t == "streak":
        min_per_week = d.get("min_per_week", 3)
        qualifying = {wk for wk, cnt in stats["weekly_counts"].items() if cnt >= min_per_week}
        return _longest_consecutive_week_run(qualifying) >= d["weeks"]

    if t == "pace":
        target_km = d["distance_km"]
        required_pace = d["max_time_min"] / target_km
        return any(
            a.distance_km and a.pace_min_per_km
            and a.distance_km >= target_km * 0.95
            and a.pace_min_per_km <= required_pace
            for a in stats["activities"]
        )

    if t == "comeback":
        gap_days = d.get("gap_days", 30)
        acts = stats["activities"]
        return any(
            a.date and b.date and (b.date - a.date).days >= gap_days
            for a, b in zip(acts, acts[1:])
        )

    if t == "time_of_day":
        if "before_hour" in d:
            return any(a.date and a.date.hour < d["before_hour"] for a in stats["activities"])
        if "after_hour" in d:
            return any(a.date and a.date.hour >= d["after_hour"] for a in stats["activities"])
        return False

    if t == "plan_adherence":
        if d.get("mode") == "perfect_week":
            return plan_stats["perfect_week"]
        if d.get("mode") == "discipline":
            return plan_stats["clean_week_streak"] >= d.get("weeks", 4)
        return False

    if t == "goal":
        return plan_stats["goal_achieved"]

    if t == "variety":
        return plan_stats["workout_type_variety"] >= d.get("min_types", 4)

    return False


def recompute_badge_achievements(user_id: int, db: Session) -> None:
    already = {
        ua.achievement_key
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
    }
    remaining = [d for d in ACHIEVEMENT_DEFS if d["key"] not in already]
    if not remaining:
        return

    stats = _collect_run_stats(user_id, db)
    plan_stats = _collect_plan_stats(user_id, db)

    newly_earned = set()
    for d in remaining:
        if d["type"] == "meta":
            continue  # мета-достижение оценивается последним, после всех остальных
        if _check(d, stats, plan_stats):
            newly_earned.add(d["key"])

    unlocked_after = already | newly_earned
    for d in remaining:
        if d["type"] != "meta":
            continue
        required = {k for k in (x["key"] for x in ACHIEVEMENT_DEFS) if k not in d.get("exclude", []) and k != d["key"]}
        if required <= unlocked_after:
            newly_earned.add(d["key"])

    for key in newly_earned:
        db.add(UserAchievement(user_id=user_id, achievement_key=key))
    db.commit()
