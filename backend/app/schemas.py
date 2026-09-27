# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime
from typing import Optional, List, Any, Literal


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
    timezone: Optional[str] = None  # IANA-имя из браузера, напр. Asia/Yekaterinburg
    altcha: Optional[str] = None  # решение ALTCHA-капчи (base64)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    altcha: Optional[str] = None  # решение ALTCHA-капчи (base64)


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
    gender: Optional[str]
    is_verified: bool
    is_admin: bool
    is_premium: bool
    premium_until: Optional[datetime]
    fitness_level: Optional[str]
    running_goal: Optional[str]
    weekly_km: Optional[float]
    training_days: Optional[int]
    max_hr: Optional[int] = None
    rest_hr: Optional[int] = None
    easy_pace_min_km: Optional[float] = None
    race_distance_km: Optional[float] = None
    race_time_min: Optional[float] = None
    timezone: Optional[str]
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=10, le=120)
    weight: Optional[float] = Field(None, gt=0, le=500)
    timezone: Optional[str] = None
    height: Optional[float] = Field(None, gt=0, le=300)
    gender: Optional[str] = None
    fitness_level: Optional[str] = None
    running_goal: Optional[str] = None
    weekly_km: Optional[float] = None
    training_days: Optional[int] = Field(None, ge=1, le=7)
    max_hr: Optional[int] = Field(None, ge=120, le=230)
    rest_hr: Optional[int] = Field(None, ge=30, le=110)
    easy_pace_min_km: Optional[float] = Field(None, ge=3.0, le=14.0)
    race_distance_km: Optional[float] = Field(None, gt=0.5, le=100)
    race_time_min: Optional[float] = Field(None, gt=1, le=1500)
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
    effort: Optional[Literal["easy", "hard"]] = None


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
    effort: Optional[str] = None
    laps:   Optional[Any]
    splits: Optional[Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityWithAnalysis(ActivityResponse):
    ai_analysis: Optional[str] = None
    ai_analysis_pending: bool = False


class ActivityImportUrl(BaseModel):
    url: str


class ActivityUpdate(BaseModel):
    date: Optional[datetime] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_heart_rate: Optional[int] = None
    calories: Optional[int] = None
    notes: Optional[str] = None
    activity_type: Optional[str] = None
    effort: Optional[Literal["easy", "hard"]] = None


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
    activity_id: Optional[int]
    notes_after: Optional[str]
    plan_structure: Optional[Any] = None
    plan_source: Optional[str] = None
    rpe: Optional[str] = None

    class Config:
        from_attributes = True


class WorkoutFeedback(BaseModel):
    rpe: Literal["easy", "ok", "hard"]


class WorkoutWithAnalysis(WorkoutResponse):
    ai_analysis: Optional[str] = None
    ai_analysis_pending: bool = False

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


# ── Support tickets ───────────────────────────────────────────────────────────
class SupportMessageOut(BaseModel):
    id: int
    is_staff: bool
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class SupportTicketSummary(BaseModel):
    id: int
    status: str                # open | closed
    created_at: datetime
    preview: str
    has_unread: bool           # есть непрочитанный ответ поддержки


class SupportTicketDetail(BaseModel):
    id: int
    status: str
    created_at: datetime
    messages: List[SupportMessageOut]


class SupportCreateRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class SupportReplyRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


# сторона сотрудника (admin tools)
class AdminSupportRow(BaseModel):
    id: int
    status: str
    created_at: datetime
    user_name: Optional[str]
    user_email: Optional[str]
    preview: str
    last_at: Optional[datetime]      # время последнего сообщения
    unread: bool                     # есть непрочитанное от пользователя
    awaiting_reply: bool             # последнее слово за пользователем (staff прочитал, но не ответил)
    can_reply: bool                  # есть реальный аккаунт-получатель


class AdminSupportList(BaseModel):
    tickets: List[AdminSupportRow]
    total: int
    page: int
    page_size: int


class SupportBadgeCounts(BaseModel):
    tickets: int                     # тредов с непрочитанным от пользователей


# Web Push
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str