# app/services/achievements.py
"""Пересчёт личных рекордов пользователя на стандартных дистанциях + разряд ЕВСК."""
from sqlalchemy.orm import Session

from app.models import Activity, PersonalRecord, User
from app.services.running_standards import match_distance, evaluate_rank


def recompute_personal_records(user_id: int, db: Session) -> None:
    """Полный пересчёт: удаляет старые записи и находит лучшую (самую быструю)
    активность на каждую стандартную дистанцию среди всех пробежек пользователя."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return

    activities = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.activity_type == "run")
        .all()
    )

    best_by_distance: dict[str, Activity] = {}
    for activity in activities:
        if not activity.distance_km or not activity.duration_min:
            continue
        matched = match_distance(activity.distance_km)
        if not matched:
            continue
        key = matched["key"]
        current_best = best_by_distance.get(key)
        if current_best is None or activity.duration_min < current_best.duration_min:
            best_by_distance[key] = activity

    db.query(PersonalRecord).filter(PersonalRecord.user_id == user_id).delete()

    for distance_key, activity in best_by_distance.items():
        time_sec = activity.duration_min * 60
        rank = evaluate_rank(user.gender, distance_key, time_sec) if user.gender else None
        db.add(PersonalRecord(
            user_id=user_id,
            distance_key=distance_key,
            activity_id=activity.id,
            time_sec=time_sec,
            achieved_rank=rank,
        ))
    db.commit()
