"""Strava webhook: verify subscription (GET) and handle events (POST)."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import User, Activity
from app.services.strava import refresh_token_if_needed, fetch_single_activity, strava_activity_to_dict
from app.services.insights_cache import invalidate_insights_cache
from app.services.achievements import recompute_personal_records

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strava", tags=["strava-webhook"])


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """Strava вызывает этот endpoint для подтверждения подписки."""
    if hub_mode != "subscribe" or hub_verify_token != settings.STRAVA_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    """Обработка событий Strava: создание/обновление/удаление активности."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    object_type = payload.get("object_type")
    aspect_type = payload.get("aspect_type")
    object_id    = payload.get("object_id")
    owner_id     = str(payload.get("owner_id", ""))

    if object_type != "activity":
        return {"status": "ignored"}

    user = db.query(User).filter(User.strava_athlete_id == owner_id).first()
    if not user:
        return {"status": "user_not_found"}

    strava_id_str = str(object_id)

    if aspect_type == "delete":
        db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.strava_id == strava_id_str,
        ).delete()
        db.commit()
        invalidate_insights_cache(user.id, db)
        recompute_personal_records(user.id, db)
        return {"status": "deleted"}

    if aspect_type in ("create", "update"):
        access_token = await refresh_token_if_needed(user)
        if not access_token:
            logger.warning("Strava webhook: no token for user %s", user.id)
            return {"status": "no_token"}
        db.commit()  # save refreshed token

        raw = await fetch_single_activity(access_token, object_id)
        if not raw:
            return {"status": "fetch_failed"}

        data = strava_activity_to_dict(raw)

        existing = db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.strava_id == strava_id_str,
        ).first()

        if existing:
            if aspect_type == "update":
                for k, v in data.items():
                    setattr(existing, k, v)
                db.commit()
                invalidate_insights_cache(user.id, db)
                recompute_personal_records(user.id, db)
            return {"status": "updated" if aspect_type == "update" else "already_exists"}

        # New activity — check time-based duplicate
        act = Activity(user_id=user.id, **data)
        dup = db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.date >= data["date"] - timedelta(minutes=1),
            Activity.date <= data["date"] + timedelta(minutes=1),
        ).first()
        if dup:
            # Link strava_id to existing
            dup.strava_id = strava_id_str
            db.commit()
            return {"status": "linked"}

        db.add(act)
        db.commit()
        invalidate_insights_cache(user.id, db)
        recompute_personal_records(user.id, db)
        return {"status": "created"}

    return {"status": "ignored"}
