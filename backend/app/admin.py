# app/admin.py
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from sqlalchemy import select

from app.database import engine, SessionLocal
from app.models import User, Activity, Goal, TrainingPlan, Workout, ChatMessage
from app.auth import verify_password, create_access_token, decode_token


# ── Аутентификация ────────────────────────────────────────────────────────────

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")   # sqladmin использует поле username
        password = form.get("password")

        db = SessionLocal()
        try:
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if not user or not verify_password(password, user.password_hash):
                return False
            if not user.is_admin:
                return False
            token = create_access_token({"sub": str(user.id)})
            request.session["admin_token"] = token
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("admin_token")
        if not token:
            return False
        payload = decode_token(token)
        if not payload:
            return False

        db = SessionLocal()
        try:
            user = db.get(User, payload["user_id"])
            return bool(user and user.is_admin)
        finally:
            db.close()


# ── ModelViews ────────────────────────────────────────────────────────────────

class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"

    column_list = [User.id, User.name, User.email, User.is_verified, User.is_admin,
                   User.is_premium, User.premium_until, User.created_at]
    column_searchable_list = [User.name, User.email]
    column_sortable_list = [User.id, User.name, User.email, User.created_at]
    column_labels = {
        "id": "ID", "name": "Имя", "email": "Email", "age": "Возраст",
        "weight": "Вес (кг)", "height": "Рост (см)", "is_verified": "Подтверждён",
        "is_admin": "Администратор", "is_premium": "Премиум",
        "premium_until": "Премиум до", "created_at": "Дата регистрации",
        "password_hash": "Хэш пароля", "verification_token": "Токен",
        "verification_token_expires": "Токен истекает", "updated_at": "Обновлён",
    }
    column_details_exclude_list = [User.password_hash, User.verification_token,
                                    User.verification_token_expires]
    form_excluded_columns = [User.password_hash, User.verification_token,
                              User.verification_token_expires,
                              User.activities, User.goals,
                              User.training_plans, User.chat_messages]
    page_size = 25


class ActivityAdmin(ModelView, model=Activity):
    name = "Пробежка"
    name_plural = "Пробежки"
    icon = "fa-solid fa-person-running"

    column_list = [Activity.id, Activity.user, Activity.date, Activity.distance_km,
                   Activity.duration_min, Activity.pace_min_per_km,
                   Activity.avg_heart_rate, Activity.calories, Activity.source]
    column_searchable_list = [Activity.notes]
    column_sortable_list = [Activity.id, Activity.date, Activity.distance_km, Activity.duration_min]
    column_labels = {
        "id": "ID", "user": "Пользователь", "date": "Дата",
        "distance_km": "Дистанция (км)", "duration_min": "Время (мин)",
        "pace_min_per_km": "Темп (мин/км)", "avg_heart_rate": "Пульс",
        "calories": "Калории", "notes": "Заметки", "source": "Источник",
        "created_at": "Создано",
    }
    page_size = 25


class GoalAdmin(ModelView, model=Goal):
    name = "Цель"
    name_plural = "Цели"
    icon = "fa-solid fa-bullseye"

    column_list = [Goal.id, Goal.user, Goal.goal_type, Goal.target_distance_km,
                   Goal.target_time_min, Goal.target_date, Goal.is_active, Goal.created_at]
    column_sortable_list = [Goal.id, Goal.created_at, Goal.target_date]
    column_labels = {
        "id": "ID", "user": "Пользователь", "goal_type": "Тип цели",
        "target_distance_km": "Дистанция (км)", "target_time_min": "Время (мин)",
        "target_date": "Дата события", "is_active": "Активна",
        "description": "Описание", "created_at": "Создана",
    }
    page_size = 25


class TrainingPlanAdmin(ModelView, model=TrainingPlan):
    name = "План тренировок"
    name_plural = "Планы тренировок"
    icon = "fa-solid fa-calendar-week"

    column_list = [TrainingPlan.id, TrainingPlan.user, TrainingPlan.goal_type,
                   TrainingPlan.week_start_date, TrainingPlan.week_end_date, TrainingPlan.is_active]
    column_labels = {
        "id": "ID", "user": "Пользователь", "goal_type": "Тип цели",
        "week_start_date": "Начало недели", "week_end_date": "Конец недели",
        "is_active": "Активен", "created_at": "Создан",
    }
    page_size = 25


class WorkoutAdmin(ModelView, model=Workout):
    name = "Тренировка"
    name_plural = "Тренировки"
    icon = "fa-solid fa-dumbbell"

    column_list = [Workout.id, Workout.training_plan, Workout.day_of_week,
                   Workout.workout_type, Workout.distance_km,
                   Workout.duration_min, Workout.completed]
    column_labels = {
        "id": "ID", "training_plan": "План", "day_of_week": "День (0=Пн)",
        "workout_type": "Тип", "description": "Описание",
        "distance_km": "Дистанция (км)", "target_pace_min_km": "Темп (мин/км)",
        "duration_min": "Время (мин)", "completed": "Выполнена",
        "notes_after": "Заметки после",
    }
    page_size = 25


class ChatMessageAdmin(ModelView, model=ChatMessage):
    name = "Сообщение чата"
    name_plural = "Сообщения чата"
    icon = "fa-solid fa-comments"

    column_list = [ChatMessage.id, ChatMessage.user, ChatMessage.role,
                   ChatMessage.context_type, ChatMessage.content, ChatMessage.created_at]
    column_searchable_list = [ChatMessage.content]
    column_sortable_list = [ChatMessage.id, ChatMessage.created_at]
    column_labels = {
        "id": "ID", "user": "Пользователь", "role": "Роль",
        "content": "Текст", "context_type": "Контекст", "created_at": "Время",
    }
    page_size = 50
    can_create = False   # сообщения создаются только через API


# ── Фабрика ───────────────────────────────────────────────────────────────────

def create_admin(app) -> Admin:
    from app.core.config import settings
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app,
        engine,
        authentication_backend=authentication_backend,
        title="AI PaceMaker — Админ",
        base_url="/admin",
    )
    for view in [UserAdmin, ActivityAdmin, GoalAdmin,
                 TrainingPlanAdmin, WorkoutAdmin, ChatMessageAdmin]:
        admin.add_view(view)
    return admin
