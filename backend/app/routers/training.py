# app/routers/training.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.database import get_db
from app.models import User, Workout, ChatMessage
from app.schemas import WorkoutResponse, WorkoutWithAnalysis
from app.dependencies import get_current_user
from app.services.ai_agent import generate_training_plan, analyze_workout_completion, replace_upcoming_workouts
from app.services.rate_limit import check_and_record
from app.services.workout_verification import find_matching_activity_for_workout, apply_verdict

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/workouts", response_model=List[WorkoutResponse])
def get_workouts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Тренировки пользователя, самые дальние по дате — первыми.

    AI никогда не генерирует тренировки дальше чем на 7 дней вперёд, поэтому
    первые 7 записей всегда и есть актуальный план — независимо от того, на
    какой день недели пришлась генерация. Дальше — история постранично, как
    в /activities."""
    return (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.planned_date.desc())
        .offset(skip).limit(limit)
        .all()
    )


@router.post("/plans/generate", response_model=List[WorkoutResponse])
async def generate_plan_ai(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI генерирует план на основе целей и истории пробежек."""
    # Проверяем rate limit (check_and_record коммитит сам — важно сделать это
    # до await ниже, а не оставлять как pending flush, см. generate_training_plan)
    check_and_record(current_user, "plan", db)

    # Берём историю чата чтобы учесть предпочтения пользователя
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()[::-1]
    )

    # Получаем тренировки от агента. generate_training_plan() освобождает
    # соединение в пул на время ожидания DeepSeek — до этого момента нарочно
    # не создаём/не флашим ничего в БД, чтобы не откатить незакоммиченные строки.
    workouts_data = await generate_training_plan(current_user, db, chat_history)

    # Заменяем тренировки на ближайшие 7 дней — уже после ответа AI
    start = datetime.now()
    replace_upcoming_workouts(current_user.id, db, workouts_data, start)
    db.commit()

    return (
        db.query(Workout)
        .filter(Workout.user_id == current_user.id)
        .order_by(Workout.planned_date.desc())
        .limit(7)
        .all()
    )


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
        background_tasks.add_task(analyze_workout_completion, workout, activity, current_user, db)

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
