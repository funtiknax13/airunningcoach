# app/routers/achievements.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PersonalRecord, Activity, UserAchievement
from app.dependencies import get_current_user
from app.services.running_standards import STANDARD_DISTANCES, RANK_LABELS, evaluate_rank, next_rank_gap
from app.services.achievement_defs import ACHIEVEMENT_DEFS

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("")
def list_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = {
        pr.distance_key: pr
        for pr in db.query(PersonalRecord).filter(PersonalRecord.user_id == current_user.id).all()
    }

    personal_records = []
    for d in STANDARD_DISTANCES:
        pr = records.get(d["key"])
        item = {
            "distance_key": d["key"],
            "distance_label": d["label"],
            "matched": pr is not None,
        }
        if pr:
            activity = db.query(Activity).filter(Activity.id == pr.activity_id).first()
            # Разряд считаем по актуальному полу пользователя на момент запроса, а не по
            # значению, сохранённому при последнем пересчёте — иначе если пол указали
            # позже, чем залогировали пробежку, разряд молча остался бы None до
            # следующей активности.
            achieved_rank, next_rank, gap_sec = (None, None, None)
            if current_user.gender:
                achieved_rank = evaluate_rank(current_user.gender, d["key"], pr.time_sec)
                next_rank, gap_sec = next_rank_gap(current_user.gender, d["key"], pr.time_sec, achieved_rank)
            item.update({
                "distance_km": pr.distance_km,
                "time_sec": pr.time_sec,
                "pace_min_km": round(pr.time_sec / 60 / d["km"], 2),
                "activity_id": pr.activity_id,
                "activity_date": activity.date.isoformat() if activity else None,
                "achieved_rank": achieved_rank,
                "achieved_rank_label": RANK_LABELS.get(achieved_rank) if achieved_rank else None,
                "next_rank": next_rank,
                "next_rank_label": RANK_LABELS.get(next_rank) if next_rank else None,
                "gap_sec": gap_sec,
            })
        personal_records.append(item)

    # "Самая длинная дистанция" — отдельная запись, не привязана к STANDARD_DISTANCES
    # и не имеет разряда (норматива на произвольную дистанцию не существует).
    longest_pr = records.get("longest")
    if longest_pr:
        activity = db.query(Activity).filter(Activity.id == longest_pr.activity_id).first()
        personal_records.append({
            "distance_key": "longest",
            "distance_label": "Самая длинная дистанция",
            "matched": True,
            "distance_km": longest_pr.distance_km,
            "time_sec": longest_pr.time_sec,
            "pace_min_km": round(longest_pr.time_sec / 60 / longest_pr.distance_km, 2) if longest_pr.distance_km else None,
            "activity_id": longest_pr.activity_id,
            "activity_date": activity.date.isoformat() if activity else None,
            "achieved_rank": None,
            "achieved_rank_label": None,
            "next_rank": None,
            "next_rank_label": None,
            "gap_sec": None,
        })

    unlocked = {
        ua.achievement_key: ua
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == current_user.id).all()
    }
    badges = []
    for d in ACHIEVEMENT_DEFS:
        ua = unlocked.get(d["key"])
        badges.append({
            "key": d["key"],
            "label": d["label"],
            "description": d["description"],
            "icon": d["icon"],
            "icon_img": f"/images/badges/{d['key']}.png",
            "unlocked": ua is not None,
            "earned_at": ua.earned_at.isoformat() if ua else None,
        })

    return {
        "gender_required": not current_user.gender,
        "personal_records": personal_records,
        "badges": badges,
    }
