# app/routers/training.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List

from app.database import get_db
from app.models import User, Workout, ChatMessage, PlanJob
from app.schemas import WorkoutResponse, WorkoutWithAnalysis
from app.dependencies import get_current_user
from app.services.ai_agent import (
    generate_training_plan, analyze_workout_completion, replace_upcoming_workouts, run_plan_job,
)
from app.services.rate_limit import check_and_record, _is_premium_active
from app.services.workout_verification import find_matching_activity_for_workout, apply_verdict

router = APIRouter(prefix="/training", tags=["training"])

# Горизонты плана в неделях. Неделя доступна всем, месяц — только премиум.
# 3 месяца намеренно убраны: план по дням на 12 недель — ложная точность, дальние
# недели всё равно перезаписываются при следующей генерации (см. обсуждение).
WEEKS_ALLOWED = {1, 4}
PREMIUM_ONLY_WEEKS = {4}


@router.get("/workouts", response_model=List[WorkoutResponse])
def get_workouts(
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Все тренировки пользователя (план + история), самые дальние по дате — первыми.

    Отдаём широким окном (до 1000): фронтенд-календарь строит из них месячную
    сетку и навигацию по прошлым месяцам целиком на клиенте, без дозапросов на
    каждый месяц. План теперь может быть на неделю/месяц/3 месяца вперёд."""
    return (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.planned_date.desc())
        .offset(skip).limit(limit)
        .all()
    )


@router.post("/plans/generate")
async def generate_plan_ai(
    background_tasks: BackgroundTasks,
    weeks: int = Query(1, description="Горизонт плана: 1 (неделя), 4 (месяц)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI генерирует план на основе целей и истории пробежек.

    weeks: 1 — неделя (всем, синхронно), 4 — месяц (только Premium, в фоне кусками —
    см. run_plan_job; ответ {"status":"running"}, готовность опрашивается через
    GET /plans/status)."""
    if weeks not in WEEKS_ALLOWED:
        raise HTTPException(status_code=400, detail="weeks должен быть 1 или 4")
    # Месяц — только премиум. Проверяем ДО списания лимита.
    if weeks in PREMIUM_ONLY_WEEKS and not _is_premium_active(current_user, db):
        raise HTTPException(status_code=403, detail="План на месяц доступен в Premium")
    days = weeks * 7

    # Проверяем rate limit (check_and_record коммитит сам — до любого await ниже).
    check_and_record(current_user, "plan", db)

    # ── Месяц: в фоне кусками ─────────────────────────────────────────────────
    # 28 дней в один вызов — ~40-60с, на грани таймаута 45с. Собираем в фоне по
    # 2-недельным кускам (каждый быстрый). Возвращаем сразу, фронт ждёт по статусу.
    if weeks in PREMIUM_ONLY_WEEKS:
        job = PlanJob(user_id=current_user.id, weeks=weeks, status="running")
        db.add(job)
        db.commit()
        db.refresh(job)
        background_tasks.add_task(run_plan_job, current_user.id, weeks, job.id)
        return {"status": "running", "weeks": weeks}

    # ── Неделя: синхронно (быстро) ────────────────────────────────────────────
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()[::-1]
    )
    workouts_data = await generate_training_plan(current_user, db, chat_history, days=days)

    # "Сегодня" — по локальному времени бегуна, не по серверу (UTC): иначе граница
    # дня могла сдвинуться на сутки. planned_date — наивная колонка, поэтому tzinfo
    # снимаем ПОСЛЕ вычисления правильного локального момента.
    try:
        now_local = datetime.now(ZoneInfo(current_user.timezone)) if current_user.timezone else datetime.now()
    except Exception:
        now_local = datetime.now()
    start = now_local.replace(tzinfo=None)
    replace_upcoming_workouts(current_user.id, db, workouts_data, start, horizon_days=days)
    db.commit()
    return {"status": "done", "weeks": weeks}


@router.get("/plans/status")
def plan_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статус последней фоновой генерации плана (для индикатора «готовится»).

    idle — задач не было; running — план собирается; done/failed — итог последней."""
    job = (
        db.query(PlanJob)
        .filter(PlanJob.user_id == current_user.id)
        .order_by(PlanJob.id.desc())
        .first()
    )
    if not job:
        return {"status": "idle"}
    return {"status": job.status, "weeks": job.weeks}


@router.put("/workouts/{workout_id}/complete", response_model=WorkoutWithAnalysis)
def complete_workout(
    workout_id: int,
    background_tasks: BackgroundTasks,
    notes: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отмечает тренировку выполненной — но не слепо: ищем подтверждающую пробежку
    и проставляем реальный статус (выполнена / частично / не подтверждена) по допуску,
    а не просто доверяем нажатию кнопки."""
    workout = (
        db.query(Workout)
        .filter(Workout.id == workout_id, Workout.user_id == current_user.id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    if workout.workout_type == "rest":
        raise HTTPException(status_code=400, detail="День отдыха не требует подтверждения")

    activity = find_matching_activity_for_workout(workout, current_user.id, db)
    apply_verdict(workout, activity)
    if notes:
        workout.notes_after = notes

    db.commit()
    db.refresh(workout)

    # Комментарий тренера — в фон, тот же принцип, что и для активностей
    # (реальный вызов DeepSeek не должен держать ответ на клик "отметить").
    pending = activity is not None
    if pending:
        background_tasks.add_task(analyze_workout_completion, workout.id, activity.id, current_user.id)

    result = WorkoutWithAnalysis.model_validate(workout)
    result.ai_analysis_pending = pending
    return result


@router.put("/workouts/{workout_id}/uncomplete", response_model=WorkoutResponse)
def uncomplete_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Снять отметку о выполнении тренировки."""
    workout = (
        db.query(Workout)
        .filter(Workout.id == workout_id, Workout.user_id == current_user.id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout.completed         = False
    workout.completion_status = "none"
    workout.activity_id       = None
    workout.notes_after       = None

    db.commit()
    db.refresh(workout)
    return workout
