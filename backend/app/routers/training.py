# app/routers/training.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, TrainingPlan, Workout, ChatMessage
from app.schemas import TrainingPlanResponse, WorkoutResponse, WorkoutWithAnalysis
from app.dependencies import get_current_user
from app.services.ai_agent import generate_training_plan, analyze_workout_completion
from app.services.rate_limit import check_and_record
from app.services.workout_verification import find_matching_activity_for_workout, apply_verdict

router = APIRouter(prefix="/training", tags=["training"])


@router.post("/plans/generate", response_model=TrainingPlanResponse)
async def generate_plan_ai(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI генерирует план на основе целей и истории пробежек."""
    # Проверяем rate limit
    check_and_record(current_user, "plan", db)

    # Деактивируем старый план
    db.query(TrainingPlan).filter(
        TrainingPlan.user_id == current_user.id,
        TrainingPlan.is_active == True,
    ).update({"is_active": False})

    start = datetime.now()
    end   = start + timedelta(days=7)

    db_plan = TrainingPlan(
        user_id=current_user.id,
        week_start_date=start,
        week_end_date=end,
        goal_type="ai_generated",
        is_active=True,
    )
    db.add(db_plan)
    db.flush()

    # Берём историю чата чтобы учесть предпочтения пользователя
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()[::-1]
    )

    # Получаем тренировки от агента
    workouts_data = await generate_training_plan(current_user, db, chat_history)

    for i, w in enumerate(workouts_data):
        offset = w.get("day_of_week", i)   # 0 = первый день плана (сегодня)
        planned = start + timedelta(days=offset)
        db.add(Workout(
            training_plan_id=db_plan.id,
            day_of_week=planned.weekday(),  # реальный день недели (0=Пн)
            planned_date=planned,
            workout_type=w.get("workout_type", "easy"),
            description=w.get("description", ""),
            distance_km=w.get("distance_km"),
            target_pace_min_km=w.get("target_pace_min_km"),
            duration_min=None,
            completion_status="none",
        ))

    db.commit()
    db.refresh(db_plan)
    db_plan.workouts = db.query(Workout).filter(
        Workout.training_plan_id == db_plan.id
    ).all()
    return db_plan


@router.get("/plans/active", response_model=TrainingPlanResponse)
def get_active_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.user_id == current_user.id,
        TrainingPlan.is_active == True,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="No active training plan")
    plan.workouts = db.query(Workout).filter(
        Workout.training_plan_id == plan.id
    ).all()
    return plan


@router.put("/workouts/{workout_id}/complete", response_model=WorkoutWithAnalysis)
def complete_workout(
    workout_id: int,
    notes: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отмечает тренировку выполненной — но не слепо: ищем подтверждающую пробежку
    и проставляем реальный статус (выполнена / частично / не подтверждена) по допуску,
    а не просто доверяем нажатию кнопки."""
    workout = (
        db.query(Workout)
        .join(TrainingPlan)
        .filter(Workout.id == workout_id, TrainingPlan.user_id == current_user.id)
        .first()
    )
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    activity = find_matching_activity_for_workout(workout, current_user.id, db)
    apply_verdict(workout, activity)
    if notes:
        workout.notes_after = notes

    db.commit()
    db.refresh(workout)

    ai_analysis = None
    if activity is not None:
        ai_analysis = analyze_workout_completion(workout, activity, current_user, db)

    result = WorkoutWithAnalysis.model_validate(workout)
    result.ai_analysis = ai_analysis or None
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
        .join(TrainingPlan)
        .filter(Workout.id == workout_id, TrainingPlan.user_id == current_user.id)
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
