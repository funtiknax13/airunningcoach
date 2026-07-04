# app/services/push_notifications.py
"""Отправка Web Push уведомлений через VAPID."""
import json
import logging

from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def _send_one(sub: PushSubscription, payload: dict) -> str:
    """Отправляет одно уведомление. Возвращает 'sent', 'stale' (подписку удалить) или 'error'."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
        )
        return "sent"
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return "stale"  # подписка истекла/отозвана — надо удалить
        logger.warning("Push send failed (status=%s): %s", status, e)
        return "error"  # временная ошибка или битая подписка — не удаляем, но и не «отправлено»


def send_push_to_user(db: Session, user_id: int, title: str, body: str, url: str = "/dashboard") -> int:
    """Отправляет уведомление на все устройства пользователя. Возвращает число реально доставленных."""
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY не настроен — push не отправлен")
        return 0

    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    payload = {"title": title, "body": body, "url": url}
    sent = 0
    for sub in subs:
        result = _send_one(sub, payload)
        if result == "sent":
            sent += 1
        elif result == "stale":
            db.delete(sub)
    db.commit()
    return sent
