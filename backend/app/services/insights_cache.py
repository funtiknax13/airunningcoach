"""
Кеш AI-инсайтов в БД.
TTL = 2 часа. Инвалидируется при добавлении пробежки или ответе чат-бота.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import InsightsCache

CACHE_TTL = timedelta(hours=24)


def get_cached_insights(user_id: int, db: Session) -> dict | None:
    """Возвращает кешированные данные если они свежее 2 часов, иначе None."""
    cutoff = datetime.now(timezone.utc) - CACHE_TTL
    row = (
        db.query(InsightsCache)
        .filter(
            InsightsCache.user_id == user_id,
            InsightsCache.created_at >= cutoff,
        )
        .first()
    )
    if row:
        return json.loads(row.payload)
    return None


def set_cached_insights(user_id: int, data: dict, db: Session) -> None:
    """Сохраняет / обновляет кеш для пользователя."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    row = db.query(InsightsCache).filter(InsightsCache.user_id == user_id).first()
    if row:
        row.payload    = payload
        row.created_at = datetime.now(timezone.utc)
    else:
        row = InsightsCache(user_id=user_id, payload=payload)
        db.add(row)
    db.commit()


def invalidate_insights_cache(user_id: int, db: Session) -> None:
    """Сбрасывает кеш — вызывается при новой пробежке или ответе чат-бота."""
    db.query(InsightsCache).filter(InsightsCache.user_id == user_id).delete()
    db.commit()
