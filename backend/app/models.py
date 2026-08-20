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
    # 0/1/2 — последний отправленный чекпоинт письма 48-часового триала
    # (0=приветствие, 1=напоминание, 2=истёк), не номер календарного дня.
    trial_last_email_stage = Column(Integer, nullable=True)
    fitness_level = Column(String(20), nullable=True)       # beginner | intermediate | advanced
    running_goal = Column(String(20), nullable=True)        # 5k | 10k | half_marathon | marathon | fitness
    weekly_km = Column(Float, nullable=True)                # текущий объём км/нед
    training_days = Column(Integer, nullable=True)          # дней в неделю
    timezone = Column(String(50), nullable=True)             # IANA-имя, напр. Asia/Yekaterinburg — для локального времени в бейджах/статистике
    onboarding_completed = Column(Boolean, default=False, nullable=False, server_default='true')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __str__(self):
        return f"{self.name} ({self.email})"

    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"
    # Почти все запросы фильтруют по user_id и сортируют по date — композитный индекс
    __table_args__ = (Index("ix_activities_user_date", "user_id", "date"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
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
    # Разбор тренировки (интервалы, тип бег/ходьба, сплит, decoupling) — считается один раз
    # при импорте (activity_analysis.compute_analysis), deferred по тому же принципу, что
    # track_points: не нужен в списковых запросах, только на детальной странице анализа.
    analysis     = deferred(Column(JSON, nullable=True))
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


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0-6 (пн-вс), совпадает с planned_date.weekday()
    workout_type = Column(String(50), nullable=False)  # easy, tempo, interval, long, recovery, rest
    description = Column(Text, nullable=False)
    distance_km = Column(Float)  # рекомендуемая дистанция
    target_pace_min_km = Column(Float)  # целевой темп
    duration_min = Column(Float)  # рекомендуемая длительность
    # Структура интервальной/фартлек-тренировки (разминка/повторы/заминка) — только для
    # таких дней, у остальных (easy/long/recovery/rest) остаётся null: {warmup_km,
    # main: [{reps, distance_m, target_pace_min_km, recovery_m, recovery_pace_min_km}], cooldown_km}
    plan_structure = Column(JSON, nullable=True)
    planned_date      = Column(DateTime, nullable=True)       # конкретная дата тренировки — единственный якорь
    completed         = Column(Boolean, default=False)
    completion_status = Column(String(20), default="none")  # none | completed | approximate | unconfirmed
    activity_id       = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)  # подтверждающая пробежка
    notes_after = Column(Text)  # заметки после выполнения

    user = relationship("User", back_populates="workouts")
    activity = relationship("Activity")

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
    activity_id   = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
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
    activity_id     = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    seen            = Column(Boolean, nullable=False, default=True, server_default='true')  # False для только что разблокированных — снимается при заходе на страницу достижений

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
    read = Column(Boolean, nullable=False, default=True, server_default='true')  # False только для фоновых AI-сообщений (auto_analysis/workout_check)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_messages")

    def __str__(self):
        preview = (self.content or '')[:40]
        return f"[{self.role}] {preview}"


class SupportTicket(Base):
    """Тред одного обращения в поддержку. Статус open|closed.

    Инбокс общий для всех админов: «прочитано» помечается на сообщениях один раз
    для всей команды (см. SupportMessage.read_at), а не персонально по агенту."""
    __tablename__ = "support_tickets"

    id                 = Column(Integer, primary_key=True, index=True)
    status             = Column(String(20), nullable=False, server_default="open")  # open | closed
    # nullable + SET NULL: если аккаунт удалят, тред остаётся историей, а не пропадает
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at         = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by = relationship("User")
    messages   = relationship(
        "SupportMessage", back_populates="ticket",
        cascade="all, delete-orphan", order_by="SupportMessage.id",
    )

    def __str__(self):
        return f"Ticket #{self.id} [{self.status}]"


class SupportMessage(Base):
    """Реплика в треде. is_staff различает автора (пользователь / сотрудник).

    read_at — момент, когда сообщение увидела ПРОТИВОПОЛОЖНАЯ сторона (ответ staff
    читает пользователь; сообщение пользователя читает staff). Общий для команды."""
    __tablename__ = "support_messages"
    __table_args__ = (Index("ix_support_messages_ticket_id", "ticket_id"),)

    id             = Column(Integer, primary_key=True, index=True)
    ticket_id      = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_staff       = Column(Boolean, nullable=False, server_default="false")
    body           = Column(Text, nullable=False)
    read_at        = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket = relationship("SupportTicket", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_user_id])

    def __str__(self):
        who = "staff" if self.is_staff else "user"
        return f"Msg #{self.id} ({who})"


class PlanJob(Base):
    """Фоновая генерация длинного плана (месяц/3 месяца) кусками.

    Длинный план не влезает в один вызов DeepSeek (таймаут 45с / потолок токенов),
    поэтому собирается в фоне по 2-недельным чанкам. Строка хранит статус, по
    которому фронт показывает «план готовится» и опрашивает готовность."""
    __tablename__ = "plan_jobs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status     = Column(String(20), nullable=False, server_default="running")  # running | done | failed
    weeks      = Column(Integer, nullable=False)
    error      = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")

    def __str__(self):
        return f"PlanJob #{self.id} {self.weeks}w [{self.status}]"