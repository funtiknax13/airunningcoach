# app/routers/admin_analytics.py
"""Внутренняя аналитика (Admin Tools): регистрации, использование ИИ, retention,
воронка. Доступ — только is_admin. Никаких новых таблиц под это не заводим —
считаем прямо по существующим (users/activities/chat_messages/api_usage/payments),
см. память по этому решению в MEMORY.md проекта.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Activity, ChatMessage, ApiUsage, Payment
from app.dependencies import get_current_admin

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


def _aware(dt: datetime | None) -> datetime | None:
    """Наивные datetime из старых строк — считаем их UTC, как и остальной код."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/overview")
def overview(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    total_users = db.query(func.count(User.id)).scalar()
    verified_users = db.query(func.count(User.id)).filter(User.is_verified == True).scalar()
    premium_active = db.query(func.count(User.id)).filter(
        User.is_premium == True,
        (User.premium_until == None) | (User.premium_until > now),
    ).scalar()
    signups_today = db.query(func.count(User.id)).filter(User.created_at >= today_start).scalar()
    signups_7d = db.query(func.count(User.id)).filter(User.created_at >= d7).scalar()
    signups_30d = db.query(func.count(User.id)).filter(User.created_at >= d30).scalar()
    dau = db.query(func.count(User.id)).filter(User.last_active_at >= today_start).scalar()
    wau = db.query(func.count(User.id)).filter(User.last_active_at >= d7).scalar()
    mau = db.query(func.count(User.id)).filter(User.last_active_at >= d30).scalar()

    # "Выручка за 30 дней" — не MRR в строгом смысле (нет учёта периода подписки
    # по каждому платежу), просто сумма успешных платежей за последние 30 дней.
    revenue_30d = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.status == "succeeded", Payment.paid_at >= d30,
    ).scalar()
    revenue_total = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.status == "succeeded",
    ).scalar()

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "premium_active": premium_active,
        "signups_today": signups_today,
        "signups_7d": signups_7d,
        "signups_30d": signups_30d,
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "revenue_30d_rub": revenue_30d,
        "revenue_total_rub": revenue_total,
    }


@router.get("/registrations")
def registrations(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Регистрации по дням за последние `days` дней, с нулями в пустых днях —
    и разбивка по utm_source (для дней, где он проставлен)."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(User.created_at, User.utm_source)
        .filter(User.created_at >= start)
        .all()
    )
    by_day: dict[str, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    for created_at, utm_source in rows:
        day = _aware(created_at).date().isoformat()
        by_day[day] += 1
        by_source[utm_source or "(direct)"] += 1

    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        series.append({"date": day, "count": by_day.get(day, 0)})

    sources = sorted(
        [{"utm_source": k, "count": v} for k, v in by_source.items()],
        key=lambda r: -r["count"],
    )
    return {"series": series, "by_source": sources}


@router.get("/ai-usage")
def ai_usage(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Обращения к ИИ по дням (chat/plan) + уникальные пользователи в день."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(ApiUsage.created_at, ApiUsage.action, ApiUsage.user_id)
        .filter(ApiUsage.created_at >= start)
        .all()
    )
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"chat": 0, "plan": 0})
    users_by_day: dict[str, set] = defaultdict(set)
    for created_at, action, user_id in rows:
        day = _aware(created_at).date().isoformat()
        if action in counts[day]:
            counts[day][action] += 1
        users_by_day[day].add(user_id)

    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        series.append({
            "date": day,
            "chat": counts[day]["chat"],
            "plan": counts[day]["plan"],
            "unique_users": len(users_by_day.get(day, ())),
        })
    return {"series": series}


@router.get("/retention")
def retention(
    weeks_back: int = Query(8, ge=1, le=26),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Недельные когорты по дате регистрации × доля вернувшихся в неделю 0-4
    после регистрации. "Вернулся" = записал тренировку или написал в чат —
    логина как отдельного события в системе нет, это лучший имеющийся прокси."""
    users = db.query(User.id, User.created_at).filter(User.created_at != None).all()
    activity_rows = db.query(Activity.user_id, Activity.created_at).all()
    chat_rows = db.query(ChatMessage.user_id, ChatMessage.created_at).filter(ChatMessage.role == "user").all()

    active_by_user: dict[int, list[datetime]] = defaultdict(list)
    for uid, dt in activity_rows:
        active_by_user[uid].append(_aware(dt))
    for uid, dt in chat_rows:
        active_by_user[uid].append(_aware(dt))

    cohorts: dict[datetime, list[int]] = defaultdict(list)
    for uid, created_at in users:
        created_at = _aware(created_at)
        week_start = (created_at - timedelta(days=created_at.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cohorts[week_start].append(uid)

    now = datetime.now(timezone.utc)
    weeks_forward = 5
    result = []
    for week_start in sorted(cohorts.keys())[-weeks_back:]:
        members = cohorts[week_start]
        row = {"cohort_week": week_start.date().isoformat(), "size": len(members), "retention": []}
        for w in range(weeks_forward):
            window_start = week_start + timedelta(weeks=w)
            window_end = window_start + timedelta(weeks=1)
            if window_start > now:
                row["retention"].append(None)
                continue
            active_count = sum(
                1 for uid in members
                if any(window_start <= d < window_end for d in active_by_user.get(uid, ()))
            )
            row["retention"].append(round(active_count / len(members) * 100, 1) if members else 0.0)
        result.append(row)
    return {"cohorts": result}


@router.get("/funnel")
def funnel(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    registered = db.query(func.count(User.id)).scalar()
    verified = db.query(func.count(User.id)).filter(User.is_verified == True).scalar()
    onboarded = db.query(func.count(User.id)).filter(User.onboarding_completed == True).scalar()
    logged_activity = db.query(func.count(func.distinct(Activity.user_id))).scalar()
    sent_ai_message = db.query(func.count(func.distinct(ApiUsage.user_id))).filter(
        ApiUsage.action == "chat"
    ).scalar()
    paid = db.query(func.count(func.distinct(Payment.user_id))).filter(
        Payment.status == "succeeded"
    ).scalar()

    steps = [
        {"step": "registered", "count": registered},
        {"step": "verified", "count": verified},
        {"step": "onboarded", "count": onboarded},
        {"step": "logged_activity", "count": logged_activity},
        {"step": "sent_ai_message", "count": sent_ai_message},
        {"step": "paid", "count": paid},
    ]
    base = registered or 1
    for s in steps:
        s["pct_of_registered"] = round(s["count"] / base * 100, 1)
    return {"steps": steps}
