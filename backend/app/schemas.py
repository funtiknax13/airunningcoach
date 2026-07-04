# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime
from typing import Optional, List, Any


# Auth schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str
    name: str = Field(..., min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=10, le=120)
    weight: Optional[float] = Field(None, gt=0, le=500)
    height: Optional[float] = Field(None, gt=0, le=300)
    lang: Optional[str] = "ru"  # язык интерфейса: "ru" | "en"

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    age: Optional[int]
    weight: Optional[float]
    height: Optional[float]
    is_verified: bool
    is_premium: bool
    premium_until: Optional[datetime]
    fitness_level: Optional[str]
    running_goal: Optional[str]
    weekly_km: Optional[float]
    training_days: Optional[int]
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=10, le=120)
    weight: Optional[float] = Field(None, gt=0, le=500)
    height: Optional[float] = Field(None, gt=0, le=300)
    fitness_level: Optional[str] = None
    running_goal: Optional[str] = None
    weekly_km: Optional[float] = None
    training_days: Optional[int] = None
    onboarding_completed: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self


class PasswordResetRequest(BaseModel):
    email: EmailStr
    lang: Optional[str] = "ru"


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetConfirm":
        if self.new_password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self


# Activity schemas
class ActivityCreate(BaseModel):
    date: datetime
    distance_km: float = Field(..., gt=0)
    duration_min: float = Field(..., gt=0)
    avg_heart_rate: Optional[int] = None
    calories: Optional[int] = None
    notes: Optional[str] = None
    activity_type: str = "run"
    source: str = "manual"


class ActivityResponse(BaseModel):
    id: int
    user_id: int
    date: datetime
    distance_km: float
    duration_min: float
    pace_min_per_km: float
    avg_heart_rate: Optional[int]
    max_heart_rate: Optional[int]
    avg_cadence:    Optional[int]
    elevation_gain: Optional[float]
    calories: Optional[int]
    notes: Optional[str]
    activity_type: str = "run"
    source: str
    laps:   Optional[Any]
    splits: Optional[Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityWithAnalysis(ActivityResponse):
    ai_analysis: Optional[str] = None


class ActivityUpdate(BaseModel):
    date: Optional[datetime] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_heart_rate: Optional[int] = None
    calories: Optional[int] = None
    notes: Optional[str] = None
    activity_type: Optional[str] = None


# Goal schemas
class GoalCreate(BaseModel):
    goal_type: str
    target_distance_km: Optional[float] = None
    target_time_min: Optional[float] = None
    target_date: Optional[datetime] = None
    description: Optional[str] = None


class GoalUpdate(BaseModel):
    goal_type: Optional[str] = None
    target_distance_km: Optional[float] = None
    target_time_min: Optional[float] = None
    target_date: Optional[datetime] = None
    description: Optional[str] = None


class GoalResponse(BaseModel):
    id: int
    user_id: int
    goal_type: str
    target_distance_km: Optional[float]
    target_time_min: Optional[float]
    target_date: Optional[datetime]
    description: Optional[str]
    is_active: bool
    is_achieved: bool
    is_abandoned: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Training plan schemas
class WorkoutCreate(BaseModel):
    day_of_week: int
    workout_type: str
    description: str
    distance_km: Optional[float] = None
    target_pace_min_km: Optional[float] = None
    duration_min: Optional[float] = None


class TrainingPlanCreate(BaseModel):
    week_start_date: datetime
    week_end_date: datetime
    goal_type: str
    workouts: List[WorkoutCreate]


class WorkoutResponse(BaseModel):
    id: int
    day_of_week: int
    planned_date: Optional[datetime]
    workout_type: str
    description: str
    distance_km: Optional[float]
    target_pace_min_km: Optional[float]
    duration_min: Optional[float]
    completed: bool
    completion_status: str
    notes_after: Optional[str]

    class Config:
        from_attributes = True


class TrainingPlanResponse(BaseModel):
    id: int
    week_start_date: datetime
    week_end_date: datetime
    goal_type: str
    is_active: bool
    created_at: datetime
    workouts: List[WorkoutResponse]

    class Config:
        from_attributes = True


# Chat schemas
class ChatMessageCreate(BaseModel):
    content: str
    context_type: Optional[str] = "general"


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    context_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# AI Chat request
class AIChatRequest(BaseModel):
    message: str
    context_type: Optional[str] = "general"
    lang: Optional[str] = "ru"


# Support contact form
class SupportContactRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=150)
    message: str = Field(..., min_length=10, max_length=3000)
    lang: Optional[str] = "ru"


# Web Push
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str