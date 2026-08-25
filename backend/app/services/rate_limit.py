"""
Rate limiting для AI-вызовов.

Базовый аккаунт:   чат — 10/день,  план — 1/день
Премиум аккаунт:   чат — 50/час,   план — 10/час

Премиум активен если is_premium=True И (premium_until IS NULL ИЛИ premium_until > now()).

Дневные лимиты (basic) сбрасываются по календарным суткам ПО ЛОКАЛЬНОМУ времени
пользователя (user.timezone), а не скользящим 24-часовым окном — иначе "8 обращений
вчера вечером + 2 сегодня утром" считались бы как 10 подряд и блокировали раньше,
чем реально наступил новый день у пользователя. Часовые лимиты (premium) остаются
скользящим окном — для "N в час" это ожидаемое поведение.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User, ApiUsage

# ── Лимиты ────────────────────────────────────────────────────────────────────

LIMITS = {
    "premium": {
        "chat": {"count": 50, "window": timedelta(hours=1)},
        "plan": {"count": 10, "window": timedelta(hours=1)},
    },
    "basic": {
        "chat": {"count": 10, "window": timedelta(hours=24)},
        "plan": {"count": 1,  "window": timedelta(hours=24)},
    },
}


def _is_premium_active(user: User, db: Session | None = None) -> bool:
    if not user.is_premium:
        return False
    if user.premium_until is None:
        return True
    until = user.premium_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    active = datetime.now(timezone.utc) < until
    if not active and db is not None:
        # «Ленивый» сброс: премиум истёк — чистим флаг прямо здесь
        user.is_premium = False
        user.premium_until = None
        db.flush()
    return active


def _tier(user: User, db: Session) -> str:
    return "premium" if _is_premium_active(user, db) else "basic"


def _window_since(user: User, cfg: dict) -> datetime:
    """Начало текущего окна лимита. Для дневных лимитов — полночь по локальному
    времени пользователя (календарный день), для часовых — скользящее окно."""
    if cfg["window"] != timedelta(hours=24):
        return datetime.now(timezone.utc) - cfg["window"]
    try:
        tz = ZoneInfo(user.timezone) if user.timezone else timezone.utc
    except Exception:
        tz = timezone.utc
    local_midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc)


def get_usage(user: User, action: str, db: Session) -> dict:
    """Возвращает текущее использование и лимит."""
    tier = _tier(user, db)
    cfg  = LIMITS[tier][action]
    since = _window_since(user, cfg)

    used = (
        db.query(ApiUsage)
        .filter(
            ApiUsage.user_id == user.id,
            ApiUsage.action == action,
            ApiUsage.created_at >= since,
        )
        .count()
    )
    return {
        "used":   used,
        "limit":  cfg["count"],
        "window": "hour" if cfg["window"] == timedelta(hours=1) else "day",
        "tier":   tier,
    }


def check_and_record(user: User, action: str, db: Session) -> None:
    """Проверяет лимит и записывает использование. Бросает 429 если лимит исчерпан."""
    info = get_usage(user, action, db)

    if info["used"] >= info["limit"]:
        window_ru = "час" if info["window"] == "hour" else "день"
        raise HTTPException(
            status_code=429,
            detail={
                "error":   "rate_limit_exceeded",
                "message": f"Лимит запросов исчерпан: {info['limit']} в {window_ru}. "
                           f"{'Обновитесь до Premium для большего лимита.' if info['tier'] == 'basic' else 'Повторите позже.'}",
                "used":    info["used"],
                "limit":   info["limit"],
                "window":  info["window"],
                "tier":    info["tier"],
            },
        )

    db.add(ApiUsage(user_id=user.id, action=action))
    # commit, не flush: сразу после этого вызывающий код обычно уходит в await
    # к DeepSeek и освобождает это соединение в пул на время ожидания — flush
    # без commit откатился бы вместе с закрытием сессии, тихо теряя счётчик.
    db.commit()
