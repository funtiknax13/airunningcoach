# app/routers/activities.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date

from app.database import get_db
from app.models import User, Activity
from app.schemas import ActivityCreate, ActivityResponse, ActivityUpdate
from app.dependencies import get_current_user
from app.services.insights_cache import invalidate_insights_cache
from app.services.achievements import recompute_achievements
from app.services.gpx_parser import parse_gpx
from app.services.fit_parser import parse_fit
from app.services.ai_agent import analyze_new_activity
from app.services.workout_verification import find_matching_workout_for_activity, apply_verdict
from app.services.safe_fetch import fetch_external_workout_file, detect_workout_format
from app.schemas import ActivityWithAnalysis, ActivityImportUrl

router = APIRouter(prefix="/activities", tags=["activities"])


def _match_workout(activity: Activity, user_id: int, db: Session) -> None:
    """Сопоставляет пробежку с тренировкой активного плана и обновляет completion_status."""
    workout = find_matching_workout_for_activity(activity, user_id, db)
    if workout:
        apply_verdict(workout, activity)


@router.post("", response_model=ActivityWithAnalysis)
def create_activity(
    activity: ActivityCreate,
    background_tasks: BackgroundTasks,
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

    # Автоанализ для сегодняшних/вчерашних тренировок — уходит в фон (реальный
    # сетевой вызов DeepSeek, может занять несколько секунд), не держим ответ клиенту.
    act_date = db_activity.date.date() if hasattr(db_activity.date, 'date') else db_activity.date
    pending = (date.today() - act_date).days <= 1
    if pending:
        background_tasks.add_task(analyze_new_activity, db_activity, current_user, db)

    result = ActivityWithAnalysis.model_validate(db_activity)
    result.ai_analysis_pending = pending
    return result


def _parse_workout_content(content: bytes, fmt: str) -> dict:
    try:
        if fmt == "gpx":
            return parse_gpx(content)
        elif fmt == "fit":
            return parse_fit(content)
        else:
            raise HTTPException(status_code=400, detail="Поддерживаются только .gpx и .fit файлы")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _save_imported_activity(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session,
    current_user: User,
) -> ActivityWithAnalysis:
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

    # Автоанализ для сегодняшних/вчерашних тренировок — в фон (см. create_activity)
    act_date = db_activity.date.date() if hasattr(db_activity.date, 'date') else db_activity.date
    pending = (date.today() - act_date).days <= 1
    if pending:
        background_tasks.add_task(analyze_new_activity, db_activity, current_user, db)

    result = ActivityWithAnalysis.model_validate(db_activity)
    result.ai_analysis_pending = pending
    return result


@router.post("/import", response_model=ActivityWithAnalysis)
async def import_activity_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Импорт пробежки из GPX или FIT файла."""
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".gpx"):
        fmt = "gpx"
    elif filename.endswith(".fit"):
        fmt = "fit"
    else:
        raise HTTPException(status_code=400, detail="Поддерживаются только .gpx и .fit файлы")

    data = _parse_workout_content(content, fmt)
    return _save_imported_activity(data, background_tasks, db, current_user)


@router.post("/import-url", response_model=ActivityWithAnalysis)
async def import_activity_from_url(
    payload: ActivityImportUrl,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Импорт пробежки по ссылке на экспорт с часов (Suunto, Garmin, Coros и т.п.)."""
    content, content_type, content_disposition = await fetch_external_workout_file(payload.url)

    fmt = detect_workout_format(content, content_type, content_disposition)
    if fmt is None:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить формат файла по ссылке — поддерживаются только .gpx и .fit",
        )

    data = _parse_workout_content(content, fmt)
    return _save_imported_activity(data, background_tasks, db, current_user)


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
