# app/routers/activities.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date

from app.database import get_db
from app.models import User, Activity, TrainingPlan, Workout
from app.schemas import ActivityCreate, ActivityResponse, ActivityUpdate
from app.dependencies import get_current_user
from app.services.insights_cache import invalidate_insights_cache
from app.services.achievements import recompute_achievements
from app.services.gpx_parser import parse_gpx
from app.services.fit_parser import parse_fit
from app.services.ai_agent import analyze_new_activity
from app.schemas import ActivityWithAnalysis

router = APIRouter(prefix="/activities", tags=["activities"])

DIST_TOLERANCE = 1.0       # ±1 км
PACE_TOLERANCE = 10 / 60   # ±10 сек/км = ±0.1667 мин/км


def _match_workout(activity: Activity, user_id: int, db: Session) -> None:
    """Сопоставляет пробежку с тренировкой активного плана и обновляет completion_status."""
    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id, TrainingPlan.is_active == True)
        .first()
    )
    if not plan:
        return

    act_date = activity.date.date() if hasattr(activity.date, 'date') else activity.date

    # Сначала ищем по planned_date (точное совпадение даты)
    workout = None
    candidates = db.query(Workout).filter(
        Workout.training_plan_id == plan.id,
        Workout.planned_date.isnot(None),
    ).all()
    for w in candidates:
        w_date = w.planned_date.date() if hasattr(w.planned_date, 'date') else w.planned_date
        if w_date == act_date:
            workout = w
            break

    # Фолбэк: старый способ по дню недели (для планов без дат)
    if not workout:
        workout = (
            db.query(Workout)
            .filter(
                Workout.training_plan_id == plan.id,
                Workout.planned_date.is_(None),
                Workout.day_of_week == activity.date.weekday(),
            )
            .first()
        )
    if not workout or workout.workout_type == "rest":
        return

    # Если у тренировки нет целевых показателей — считаем «выполнено»
    has_dist = workout.distance_km is not None
    has_pace = workout.target_pace_min_km is not None

    dist_ok = (not has_dist) or (abs(activity.distance_km - workout.distance_km) <= DIST_TOLERANCE)
    pace_ok = (not has_pace) or (
        activity.pace_min_per_km is not None
        and abs(activity.pace_min_per_km - workout.target_pace_min_km) <= PACE_TOLERANCE
    )

    if dist_ok and pace_ok:
        workout.completion_status = "completed"
    else:
        workout.completion_status = "approximate"

    workout.completed = True


@router.post("", response_model=ActivityWithAnalysis)
def create_activity(
    activity: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pace = activity.duration_min / activity.distance_km if activity.distance_km > 0 else 0
    db_activity = Activity(
        user_id=current_user.id,
        date=activity.date,
        distance_km=activity.distance_km,
        duration_min=activity.duration_min,
        pace_min_per_km=pace,
        avg_heart_rate=activity.avg_heart_rate,
        calories=activity.calories,
        notes=activity.notes,
        activity_type=activity.activity_type,
        source=activity.source,
    )
    db.add(db_activity)
    db.flush()
    _match_workout(db_activity, current_user.id, db)
    db.commit()
    db.refresh(db_activity)

    invalidate_insights_cache(current_user.id, db)
    recompute_achievements(current_user.id, db)

    # Автоанализ для сегодняшних/вчерашних тренировок
    ai_analysis = None
    act_date = db_activity.date.date() if hasattr(db_activity.date, 'date') else db_activity.date
    if (date.today() - act_date).days <= 1:
        ai_analysis = analyze_new_activity(db_activity, current_user, db)

    result = ActivityWithAnalysis.model_validate(db_activity)
    result.ai_analysis = ai_analysis or None
    return result


@router.post("/import", response_model=ActivityWithAnalysis)
async def import_activity_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Импорт пробежки из GPX или FIT файла."""
    content = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".gpx"):
            data = parse_gpx(content)
        elif filename.endswith(".fit"):
            data = parse_fit(content)
        else:
            raise HTTPException(status_code=400, detail="Поддерживаются только .gpx и .fit файлы")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Проверка дублирования по времени старта (±1 минута)
    start_time = data["date"]
    from datetime import timedelta
    duplicate = db.query(Activity).filter(
        Activity.user_id == current_user.id,
        Activity.date >= start_time - timedelta(minutes=1),
        Activity.date <= start_time + timedelta(minutes=1),
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_activity",
                "existing_id": duplicate.id,
                "existing_date": duplicate.date.isoformat(),
            }
        )

    pace = data["duration_min"] / data["distance_km"] if data["distance_km"] > 0 else 0
    db_activity = Activity(
        user_id=current_user.id,
        date=data["date"],
        distance_km=data["distance_km"],
        duration_min=data["duration_min"],
        pace_min_per_km=pace,
        avg_heart_rate=data.get("avg_heart_rate"),
        max_heart_rate=data.get("max_heart_rate"),
        avg_cadence=data.get("avg_cadence"),
        elevation_gain=data.get("elevation_gain"),
        calories=data.get("calories"),
        laps=data.get("laps"),
        splits=data.get("splits"),
        track_points=data.get("track_points"),
        activity_type=data.get("activity_type", "run"),
        source=data["source"],
    )
    db.add(db_activity)
    db.flush()
    _match_workout(db_activity, current_user.id, db)
    db.commit()
    db.refresh(db_activity)

    invalidate_insights_cache(current_user.id, db)
    recompute_achievements(current_user.id, db)

    # Автоанализ для сегодняшних/вчерашних тренировок
    ai_analysis = None
    act_date = db_activity.date.date() if hasattr(db_activity.date, 'date') else db_activity.date
    if (date.today() - act_date).days <= 1:
        # Блокирующий вызов DeepSeek → в threadpool, чтобы не морозить event loop
        ai_analysis = await run_in_threadpool(
            analyze_new_activity, db_activity, current_user, db
        )

    result = ActivityWithAnalysis.model_validate(db_activity)
    result.ai_analysis = ai_analysis or None
    return result


@router.get("/stats")
def get_monthly_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Быстрая статистика за текущий месяц — чистый SQL, без LLM."""
    today = date.today()
    month_start = today.replace(day=1)

    activities = db.query(Activity).filter(
        Activity.user_id == current_user.id,
        Activity.activity_type == "run",
        Activity.date >= datetime.combine(month_start, datetime.min.time()),
    ).all()

    total_distance = sum(a.distance_km  for a in activities)
    total_time     = sum(a.duration_min for a in activities)
    avg_pace       = total_time / total_distance if total_distance > 0 else 0

    # Прошлый месяц для сравнения
    if month_start.month == 1:
        prev_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        prev_start = month_start.replace(month=month_start.month - 1)

    prev_activities = db.query(Activity).filter(
        Activity.user_id == current_user.id,
        Activity.activity_type == "run",
        Activity.date >= datetime.combine(prev_start, datetime.min.time()),
        Activity.date < datetime.combine(month_start, datetime.min.time()),
    ).all()
    prev_distance = sum(a.distance_km for a in prev_activities)

    return {
        "period": month_start.strftime("%B %Y"),
        "total_distance_km":   round(total_distance, 1),
        "total_time_min":      round(total_time),
        "average_pace_min_km": round(avg_pace, 2),
        "activities_count":    len(activities),
        "prev_distance_km":    round(prev_distance, 1),
        "distance_delta":      round(total_distance - prev_distance, 1),
    }


@router.get("", response_model=List[ActivityResponse])
def get_activities(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Activity)
        .filter(Activity.user_id == current_user.id)
        .order_by(Activity.date.desc())
        .offset(skip).limit(limit)
        .all()
    )


@router.get("/{activity_id}/detail")
def get_activity_detail(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Полные данные активности включая GPS-трек."""
    activity = db.query(Activity).filter(
        Activity.id == activity_id, Activity.user_id == current_user.id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {
        "id":             activity.id,
        "date":           activity.date,
        "distance_km":    activity.distance_km,
        "duration_min":   activity.duration_min,
        "pace_min_per_km": activity.pace_min_per_km,
        "avg_heart_rate": activity.avg_heart_rate,
        "max_heart_rate": activity.max_heart_rate,
        "avg_cadence":    activity.avg_cadence,
        "elevation_gain": activity.elevation_gain,
        "calories":       activity.calories,
        "notes":          activity.notes,
        "source":         activity.source,
        "laps":           activity.laps,
        "splits":         activity.splits,
        "track_points":   activity.track_points,
    }


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id, Activity.user_id == current_user.id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.put("/{activity_id}", response_model=ActivityResponse)
def update_activity(
    activity_id: int,
    activity_update: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id, Activity.user_id == current_user.id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    update_data = activity_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)

    if "distance_km" in update_data or "duration_min" in update_data:
        if activity.distance_km and activity.duration_min:
            activity.pace_min_per_km = activity.duration_min / activity.distance_km

    _match_workout(activity, current_user.id, db)
    db.commit()
    db.refresh(activity)

    invalidate_insights_cache(current_user.id, db)
    recompute_achievements(current_user.id, db)

    return activity


@router.delete("/{activity_id}")
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id, Activity.user_id == current_user.id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()

    invalidate_insights_cache(current_user.id, db)
    recompute_achievements(current_user.id, db)

    return {"message": "Activity deleted"}
