# app/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON, Index
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer)
    weight = Column(Float)  # в кг
    height = Column(Float)  # в см
    gender = Column(String(10), nullable=True)  # male | female — нужен для разрядов ЕВСК
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(64), nullable=True, index=True)
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String(64), nullable=True, index=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    google_id = Column(String(128), nullable=True, unique=True, index=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_until = Column(DateTime(timezone=True), nullable=True)
    trial_last_email_day = Column(Integer, nullable=True)
    fitness_level = Column(String(20), nullable=True)       # beginner | intermediate | advanced
    running_goal = Column(String(20), nullable=True)        # 5k | 10k | half_marathon | marathon | fitness
    weekly_km = Column(Float, nullable=True)                # текущий объём км/нед
    training_days = Column(Integer, nullable=True)          # дней в неделю
    onboarding_completed = Column(Boolean, default=False, nullable=False, server_default='true')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __str__(self):
        return f"{self.name} ({self.email})"

    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    training_plans = relationship("TrainingPlan", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"
    # Почти все запросы фильтруют по user_id и сортируют по date — композитный индекс
    __table_args__ = (Index("ix_activities_user_date", "user_id", "date"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    distance_km = Column(Float, nullable=False)  # дистанция в км
    duration_min = Column(Float, nullable=False)  # время в минутах
    pace_min_per_km = Column(Float)  # темп (мин/км) - вычисляемое поле
    avg_heart_rate = Column(Integer)            # средний пульс
    max_heart_rate = Column(Integer)            # максимальный пульс
    avg_cadence    = Column(Integer)            # средний каденс (шаг/мин)
    calories       = Column(Integer)            # калории
    elevation_gain = Column(Float)              # набор высоты (метры)
    notes          = Column(Text)               # заметки
    activity_type  = Column(String(50), default="run")   # run, ride, walk, hike, swim, strength, workout, other
    source         = Column(String(50), default="manual")  # manual, gpx, fit
    # Детальные данные (хранятся как JSON)
    laps         = Column(JSON, nullable=True)  # [{num,dist_km,dur_min,pace,avg_hr,max_hr}]
    splits       = Column(JSON, nullable=True)  # [{km,pace,avg_hr}]  – по километрам
    # track_points (полный GPS-трек) большой и нужен только на детальной карте —
    # deferred: НЕ грузится при обычных db.query(Activity), только при явном обращении.
    track_points = deferred(Column(JSON, nullable=True))  # [{t,lat,lon,ele,hr,dist}]
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="activities")

    def __str__(self):
        return f"{self.distance_km} км — {self.date.strftime('%d.%m.%Y') if self.date else ''}"


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    goal_type = Column(String(50), nullable=False)  # half_marathon, full_marathon, 10k, 5k, custom
    target_distance_km = Column(Float)  # целевая дистанция
    target_time_min = Column(Float)  # целевое время в минутах
    target_date = Column(DateTime)  # дата целевого события
    description = Column(Text)
    is_active   = Column(Boolean, default=True)
    is_achieved = Column(Boolean, default=False, nullable=False)
    is_abandoned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="goals")

    def __str__(self):
        labels = {'half_marathon': 'Полумарафон', 'full_marathon': 'Марафон',
                  '10k': '10 км', '5k': '5 км', 'custom': 'Своя цель'}
        return labels.get(self.goal_type, self.goal_type)


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start_date = Column(DateTime, nullable=False)
    week_end_date = Column(DateTime, nullable=False)
    goal_type = Column(String(50))  # для какой цели создан план
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="training_plans")
    workouts = relationship("Workout", back_populates="training_plan", cascade="all, delete-orphan")

    def __str__(self):
        start = self.week_start_date.strftime('%d.%m.%Y') if self.week_start_date else '?'
        return f"План с {start}"


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    training_plan_id = Column(Integer, ForeignKey("training_plans.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0-6 (пн-вс)
    workout_type = Column(String(50), nullable=False)  # easy, tempo, interval, long, recovery, rest
    description = Column(Text, nullable=False)
    distance_km = Column(Float)  # рекомендуемая дистанция
    target_pace_min_km = Column(Float)  # целевой темп
    duration_min = Column(Float)  # рекомендуемая длительность
    planned_date      = Column(DateTime, nullable=True)       # конкретная дата тренировки
    completed         = Column(Boolean, default=False)
    completion_status = Column(String(20), default="none")  # none | completed | approximate
    notes_after = Column(Text)  # заметки после выполнения

    training_plan = relationship("TrainingPlan", back_populates="workouts")

    DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    def __str__(self):
        day = self.DAYS[self.day_of_week] if self.day_of_week is not None else '?'
        return f"{day} — {self.workout_type}"


class Payment(Base):
    """История платежей через ЮКассу."""
    __tablename__ = "payments"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    yookassa_id   = Column(String(64), unique=True, nullable=False, index=True)
    plan          = Column(String(20), nullable=False)   # month | quarter | year
    amount        = Column(Integer,  nullable=False)     # в рублях
    status        = Column(String(20), default="pending") # pending | succeeded | canceled
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    paid_at       = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class ApiUsage(Base):
    """Журнал AI-вызовов для rate limiting."""
    __tablename__ = "api_usage"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action     = Column(String(20), nullable=False)   # 'chat' | 'plan'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PersonalRecord(Base):
    """Личный рекорд на стандартной дистанции + достигнутый разряд ЕВСК."""
    __tablename__ = "personal_records"
    __table_args__ = (Index("ix_pr_user_distance", "user_id", "distance_key", unique=True),)

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    distance_key  = Column(String(30), nullable=False)  # ...marathon | "longest" (самая длинная дистанция, без разряда)
    activity_id   = Column(Integer, ForeignKey("activities.id"), nullable=False)
    distance_km   = Column(Float, nullable=True)  # фактическая дистанция активности
    time_sec      = Column(Float, nullable=False)
    achieved_rank = Column(String(10), nullable=True)  # msmk | ms | kms | r1 | r2 | r3 | None
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User")
    activity = relationship("Activity")

    def __str__(self):
        return f"PR user={self.user_id} {self.distance_key}={self.time_sec}s ({self.achieved_rank})"


class UserAchievement(Base):
    """Разблокированное достижение — раз получено, не отзывается (даже если породившая
    активность позже удалена/изменена — это история, а не текущий рекорд)."""
    __tablename__ = "user_achievements"
    __table_args__ = (Index("ix_ua_user_key", "user_id", "achievement_key", unique=True),)

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    achievement_key = Column(String(40), nullable=False)
    earned_at       = Column(DateTime(timezone=True), server_default=func.now())
    activity_id     = Column(Integer, ForeignKey("activities.id"), nullable=True)

    user = relationship("User")
    activity = relationship("Activity")

    def __str__(self):
        return f"Achievement user={self.user_id} {self.achievement_key}"


class InsightsCache(Base):
    """Кеш AI-инсайтов — один ряд на пользователя, TTL 2 часа."""
    __tablename__ = "insights_cache"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    payload    = Column(Text, nullable=False)   # JSON-строка с полным ответом дашборда
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    def __str__(self):
        return f"InsightsCache user_id={self.user_id}"


class PushSubscription(Base):
    """Web Push подписка браузера — один пользователь может иметь несколько (разные устройства)."""
    __tablename__ = "push_subscriptions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint   = Column(Text, unique=True, nullable=False)
    p256dh     = Column(String(255), nullable=False)
    auth       = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    # История и контекст AI фильтруют по user_id и сортируют по created_at
    __table_args__ = (Index("ix_chat_messages_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, ai, system
    content = Column(Text, nullable=False)
    context_type = Column(String(50))  # training, nutrition, injury, general
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_messages")

    def __str__(self):
        preview = (self.content or '')[:40]
        return f"[{self.role}] {preview}"