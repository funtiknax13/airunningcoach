"""
Фоновые задачи для email-цепочки Premium-триала.

День  1 — приветствие + список возможностей
День  5 — подсказки как использовать, напоминание об остатке
День 13 — предупреждение: остался 1 день
День 14 — триал истёк, переход на Basic

Планировщик запускается вместе с FastAPI (lifespan).
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.services.email import (
    send_trial_day1_email,
    send_trial_day5_email,
    send_trial_day13_email,
    send_trial_expired_email,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def _get_trial_day(user: User) -> int | None:
    """Возвращает номер дня триала (1-based) или None если триал не активен."""
    if not user.created_at or not user.premium_until:
        return None
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    return delta.days + 1  # день 1 = первые 24 ч после регистрации


def _is_trial_user(user: User) -> bool:
    """Пользователь на триале: premium_until установлен и ≤ 14 дней от регистрации."""
    if not user.premium_until or not user.created_at:
        return False
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    trial_end = created + timedelta(days=14)
    until = user.premium_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    # premium_until близко к trial_end → это триальный пользователь
    return abs((until - trial_end).total_seconds()) < 86_400 * 2


def _days_left(user: User) -> int:
    """Дней до конца триала."""
    until = user.premium_until
    if not until:
        return 0
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return max(0, (until - datetime.now(timezone.utc)).days)


async def _run_trial_emails() -> None:
    """Запускается каждый час. Находит пользователей на нужном дне и отправляет письмо."""
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        users = db.query(User).filter(
            User.is_verified == True,
            User.premium_until != None,
        ).all()

        for user in users:
            if not _is_trial_user(user):
                continue

            day = _get_trial_day(user)
            if day is None:
                continue

            lang = "ru"  # TODO: хранить lang в профиле пользователя
            left = _days_left(user)

            try:
                if day == 1:
                    await send_trial_day1_email(user.email, user.name, lang)
                    logger.info("Trial day1 email → %s", user.email)

                elif day == 5:
                    await send_trial_day5_email(user.email, user.name, left, lang)
                    logger.info("Trial day5 email → %s", user.email)

                elif day == 13:
                    await send_trial_day13_email(user.email, user.name, left, lang)
                    logger.info("Trial day13 email → %s", user.email)

                elif day == 14:
                    await send_trial_expired_email(user.email, user.name, lang)
                    logger.info("Trial expired email → %s", user.email)

            except Exception as exc:
                logger.error("Trial email failed for %s (day %d): %s", user.email, day, exc)

    finally:
        db.close()


def start_scheduler() -> None:
    scheduler.add_job(
        _run_trial_emails,
        trigger="interval",
        hours=1,
        id="trial_emails",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),  # первый запуск через 30 сек
    )
    scheduler.start()
    logger.info("Trial email scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Trial email scheduler stopped")
