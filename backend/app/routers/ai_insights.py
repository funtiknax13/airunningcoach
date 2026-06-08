# app/routers/ai_insights.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, Activity, Goal
from app.dependencies import get_current_user
from app.services.ai_agent import generate_insights
from app.services.insights_cache import get_cached_insights, set_cached_insights

router = APIRouter(prefix="/ai-insights", tags=["ai_insights"])


@router.get("/dashboard")
async def get_ai_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── Проверяем кеш (TTL 2 часа) ──────────────────────────────
    cached = get_cached_insights(current_user.id, db)
    if cached:
        return cached

    # ── Кеш устарел или отсутствует — считаем заново ────────────
    since = datetime.now() - timedelta(days=30)
    activities = db.query(Activity).filter(
        Activity.user_id == current_user.id,
        Activity.date >= since,
    ).order_by(Activity.date).all()

    total_distance = sum(a.distance_km  for a in activities)
    total_time     = sum(a.duration_min for a in activities)
    avg_pace       = total_time / total_distance if total_distance > 0 else 0

    active_goal = db.query(Goal).filter(
        Goal.user_id == current_user.id,
        Goal.is_active == True,
    ).first()

    insights = await generate_insights(current_user, db)

    result = {
        "user_name": current_user.name,
        "statistics": {
            "total_distance_km":       round(total_distance, 1),
            "total_time_min":          round(total_time, 1),
            "average_pace_min_km":     round(avg_pace, 2),
            "activities_count":        len(activities),
            "average_weekly_distance": round(total_distance / 4, 1),
        },
        "active_goal": {
            "type":        active_goal.goal_type,
            "description": active_goal.description or "",
        } if active_goal else None,
        "ai_insights": insights,
    }

    # ── Сохраняем в кеш ─────────────────────────────────────────
    set_cached_insights(current_user.id, result, db)
    return result
