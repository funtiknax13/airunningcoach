# app/services/badge_achievements.py
"""Разблокировка «достижений» (бейджей) — односторонний храповик: только
добавляет новые заработанные достижения, никогда не отзывает уже полученные."""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Activity, UserAchievement
from app.services.achievement_defs import ACHIEVEMENT_DEFS


def recompute_badge_achievements(user_id: int, db: Session) -> None:
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.activity_type == "run")
        .all()
    )

    total_count = len(activities)
    max_distance = max((a.distance_km or 0 for a in activities), default=0)

    monthly_totals: dict[tuple[int, int], float] = defaultdict(float)
    for a in activities:
        if not a.date or not a.distance_km:
            continue
        monthly_totals[(a.date.year, a.date.month)] += a.distance_km
    best_month = max(monthly_totals.values(), default=0)

    already = {
        ua.achievement_key
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
    }

    for d in ACHIEVEMENT_DEFS:
        if d["key"] in already:
            continue
        earned = (
            (d["type"] == "count" and total_count >= d["value"]) or
            (d["type"] == "distance" and max_distance >= d["value"]) or
            (d["type"] == "monthly_volume" and best_month >= d["value"])
        )
        if earned:
            db.add(UserAchievement(user_id=user_id, achievement_key=d["key"]))

    db.commit()
