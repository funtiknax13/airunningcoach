# app/routers/push.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PushSubscription
from app.schemas import PushSubscribeRequest, PushUnsubscribeRequest
from app.dependencies import get_current_user
from app.core.config import settings
from app.services.push_notifications import send_push_to_user

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    return {"key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
def subscribe(
    data: PushSubscribeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == data.endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = data.keys.p256dh
        existing.auth = data.keys.auth
    else:
        db.add(PushSubscription(
            user_id=current_user.id,
            endpoint=data.endpoint,
            p256dh=data.keys.p256dh,
            auth=data.keys.auth,
        ))
    db.commit()
    return {"message": "subscribed"}


@router.post("/unsubscribe")
def unsubscribe(
    data: PushUnsubscribeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == data.endpoint,
        PushSubscription.user_id == current_user.id,
    ).delete()
    db.commit()
    return {"message": "unsubscribed"}


@router.post("/test")
def send_test(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sent = send_push_to_user(
        db, current_user.id,
        title="AI RunningCoach",
        body="Уведомления включены! Мы будем напоминать о тренировках.",
    )
    return {"sent": sent}
