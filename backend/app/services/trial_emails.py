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

from app.database import SessionLocal, engine
from app.models import User, Activity, Workout
from app.services.email import (
    send_trial_day1_email,
    send_trial_day5_email,
    send_trial_day13_email,
    send_trial_expired_email,
    send_weekly_stats_email,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

# Соединение держим открытым, пока держим advisory-lock (лок живёт сколько живёт сессия).
_lock_conn = None
_SCHED_LOCK_ID = 915_623  # произвольный уникальный ключ для pg_try_advisory_lock


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

            # Не отправляем письмо, если для этого дня уже отправлено
            if user.trial_last_email_day is not None and user.trial_last_email_day >= day:
                continue

            target_day = None
            try:
                if day == 1:
                    await send_trial_day1_email(user.email, user.name, lang)
                    logger.info("Trial day1 email → %s", user.email)
                    target_day = 1

                elif day == 5:
                    await send_trial_day5_email(user.email, user.name, left, lang)
                    logger.info("Trial day5 email → %s", user.email)
                    target_day = 5

                elif day == 13:
                    await send_trial_day13_email(user.email, user.name, left, lang)
                    logger.info("Trial day13 email → %s", user.email)
                    target_day = 13

                elif day == 14:
                    await send_trial_expired_email(user.email, user.name, lang)
                    logger.info("Trial expired email → %s", user.email)
                    target_day = 14

                if target_day is not None:
                    user.trial_last_email_day = target_day
                    db.commit()

            except Exception as exc:
                logger.error("Trial email failed for %s (day %d): %s", user.email, day, exc)

    finally:
        db.close()


_WORKOUT_TYPE_RU = {
    "easy": "Лёгкий бег", "tempo": "Темповая", "interval": "Интервалы",
    "long": "Длинная", "recovery": "Восстановление", "rest": "Отдых",
}

async def _run_weekly_stats() -> None:
    """Каждое воскресенье в 21:00 МСК (18:00 UTC): отправляем статистику за неделю."""
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)
        prev_week_start = now - timedelta(days=14)
        next_week_end = now + timedelta(days=7)
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        users = db.query(User).filter(User.is_verified == True).all()
        for user in users:
            try:
                week_runs = db.query(Activity).filter(
                    Activity.user_id == user.id,
                    Activity.activity_type == "run",
                    Activity.date >= week_start,
                ).all()

                # Тренировки на следующие 7 дней
                workouts = db.query(Workout).filter(
                    Workout.user_id == user.id,
                    Workout.planned_date >= now,
                    Workout.planned_date <= next_week_end,
                    Workout.completion_status == "none",
                ).order_by(Workout.planned_date).all()

                plan_items: list[dict] = []
                for w in workouts:
                    if w.planned_date:
                        wd = w.planned_date.weekday()
                        date_str = f"{day_names[wd]} {w.planned_date.strftime('%d.%m')}"
                    else:
                        date_str = day_names[w.day_of_week]
                    plan_items.append({
                        "date": date_str,
                        "type": _WORKOUT_TYPE_RU.get(w.workout_type, w.workout_type),
                        "desc": w.description,
                        "km": w.distance_km,
                    })

                # Отправляем если есть пробежки за неделю ИЛИ есть предстоящие тренировки
                if not week_runs and not plan_items:
                    continue

                prev_runs = db.query(Activity).filter(
                    Activity.user_id == user.id,
                    Activity.activity_type == "run",
                    Activity.date >= prev_week_start,
                    Activity.date < week_start,
                ).all()

                total_km = sum(a.distance_km for a in week_runs)
                prev_km = sum(a.distance_km for a in prev_runs)
                paces = [a.pace_min_per_km for a in week_runs if a.pace_min_per_km]
                avg_pace = sum(paces) / len(paces) if paces else None

                await send_weekly_stats_email(
                    to_email=user.email,
                    name=user.name,
                    runs=len(week_runs),
                    total_km=total_km,
                    avg_pace=avg_pace,
                    prev_km=prev_km,
                    plan_items=plan_items,
                    lang="ru",
                )
                logger.info("Weekly stats email → %s", user.email)
            except Exception as exc:
                logger.error("Weekly stats email failed for %s: %s", user.email, exc)
    finally:
        db.close()


def _try_acquire_lock() -> bool:
    """Берёт advisory-lock Postgres. True — этот воркер ведущий (запускает планировщик).

    SQLite (локалка) лока не имеет — всегда True. На postgres лок гарантирует,
    что при нескольких воркерах планировщик работает ровно в одном.
    """
    global _lock_conn
    if "sqlite" in str(engine.url):
        return True
    try:
        conn = engine.raw_connection()
        cur = conn.cursor()
        cur.execute("SELECT pg_try_advisory_lock(%s)", (_SCHED_LOCK_ID,))
        got = bool(cur.fetchone()[0])
        cur.close()
        if got:
            _lock_conn = conn  # держим соединение → держим лок до остановки воркера
        else:
            conn.close()
        return got
    except Exception as exc:
        logger.error("Scheduler lock acquire failed: %s", exc)
        return False


def start_scheduler() -> None:
    if not _try_acquire_lock():
        logger.info("Trial scheduler: лок у другого воркера — пропускаем запуск")
        return
    scheduler.add_job(
        _run_trial_emails,
        trigger="interval",
        hours=1,
        id="trial_emails",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    # Еженедельная статистика — каждое воскресенье в 18:00 UTC (21:00 МСК)
    scheduler.add_job(
        _run_weekly_stats,
        trigger="cron",
        day_of_week="sun",
        hour=18,
        minute=0,
        id="weekly_stats",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Trial email scheduler started")


def stop_scheduler() -> None:
    global _lock_conn
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Trial email scheduler stopped")
    if _lock_conn is not None:
        try:
            _lock_conn.close()  # отпускаем advisory-lock
        except Exception:
            pass
        _lock_conn = None
