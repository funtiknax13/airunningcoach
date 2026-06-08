# app/routers/goals.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, Goal
from app.schemas import GoalCreate, GoalUpdate, GoalResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/goals", tags=["goals"])

DIST_TOLERANCE  = 1.0      # ±1 км
PACE_TOLERANCE  = 10 / 60  # ±10 сек/км → ±0.1667 мин/км


def _get_own_goal(goal_id: int, user: User, db: Session) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    return goal


@router.post("", response_model=GoalResponse)
def create_goal(
    goal: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Создаём новую цель — существующие НЕ деактивируем (можно держать несколько)
    db_goal = Goal(
        user_id=current_user.id,
        goal_type=goal.goal_type,
        target_distance_km=goal.target_distance_km,
        target_time_min=goal.target_time_min,
        target_date=goal.target_date,
        description=goal.description,
        is_active=True,
        is_achieved=False,
        is_abandoned=False,
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal


@router.get("", response_model=List[GoalResponse])
def get_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Goal)
        .filter(Goal.user_id == current_user.id)
        .order_by(Goal.is_active.desc(), Goal.created_at.desc())
        .all()
    )


@router.get("/active", response_model=GoalResponse)
def get_active_goal(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = (
        db.query(Goal)
        .filter(Goal.user_id == current_user.id, Goal.is_active == True)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal found")
    return goal


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    data: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_own_goal(goal_id, current_user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}/achieve", response_model=GoalResponse)
def achieve_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_own_goal(goal_id, current_user, db)
    goal.is_achieved = True
    goal.is_active   = False
    goal.is_abandoned = False
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}/abandon", response_model=GoalResponse)
def abandon_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_own_goal(goal_id, current_user, db)
    goal.is_abandoned = True
    goal.is_active    = False
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}/reactivate", response_model=GoalResponse)
def reactivate_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_own_goal(goal_id, current_user, db)
    goal.is_active    = True
    goal.is_achieved  = False
    goal.is_abandoned = False
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_own_goal(goal_id, current_user, db)
    db.delete(goal)
    db.commit()
