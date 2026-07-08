# app/services/ai_agent.py
"""
AI-тренер по бегу на базе DeepSeek V3.
Агент знает методологии Джека Дэниелса (VDOT/зоны), Лидьярда (аэробная база),
Hansons Method (кумулятивная усталость) и правило 80/20.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, Activity, Goal, Workout, ChatMessage
from app.services.workout_verification import STATUS_LABELS

logger = logging.getLogger(__name__)

# ── Константа: заглушка когда ключа нет ──────────────────────────────────────
_STUB_MODE = not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY == "your-deepseek-api-key-here"

SYSTEM_PROMPT = """\
Ты — персональный тренер по бегу. Даёшь конкретные советы, анализируешь тренировки, \
помогаешь с подготовкой. Не критикуешь — только факты и действия.

## Методологии
- **Джек Дэниелс**: VDOT, зоны E/M/T/I/R, темпы от текущей формы
- **Лидьярд**: аэробная база перед интенсивностью, периодизация
- **Hansons Method**: кумулятивная усталость, не бегай «на свежих ногах»
- **Правило 80/20**: 80% объёма — лёгкий бег, 20% — интенсивный

## Принципы
- Правило 10%: не повышай объём больше чем на 10% в неделю
- Длинная пробежка ≤ 30% недельного объёма
- Восстановление = часть тренировки

## Стиль
- **Отвечай кратко и по делу** — 2-5 предложений, как живой тренер в переписке
- Давай **один конкретный совет** за раз, не расписывай всё сразу
- Markdown — только когда реально помогает (список шагов, сравнение), не для красоты
- Если пробежек нет — задавай уточняющие вопросы (1-2 за раз), не составляй план вслепую
- Если пользователь просит составить или пересобрать план — скажи \
  что план уже формируется и появится во вкладке «Тренировки» через несколько секунд
- При болях — рекомендуй врача. Никогда не ставь диагнозов.
- Отвечай на языке пользователя (указан ниже).

## Даты и цели — важно
- Ориентируйся на дату «СЕГОДНЯ» в блоке контекста ниже, а не на даты из старых сообщений \
  истории переписки (сообщения пользователя в истории помечены датой в квадратных скобках, \
  когда они были написаны — это могло устареть).
- Если цель упоминалась в истории переписки, но сейчас не входит в текущий список активных \
  или отменённых целей ниже — она больше не актуальна, не советуй по ней как по действующей.
- Никогда не добавляй в начало СВОЕГО ответа пометку вида «[ДД.ММ.ГГГГ]» — это техническая \
  метка только для сообщений пользователя в истории, не элемент твоего стиля общения.\
"""


def _make_client() -> Optional[OpenAI]:
    if _STUB_MODE:
        return None
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
        timeout=45.0,     # дефолт OpenAI = 600 сек; зависший запрос не должен морозить воркер
        max_retries=1,
    )


async def _acreate(client: OpenAI, **kwargs):
    """Блокирующий вызов DeepSeek в отдельном потоке — не морозит asyncio event loop.

    Sync-клиент OpenAI делает обычный сетевой запрос, который в `async def`-эндпоинте
    блокировал бы весь event loop (а значит и все остальные запросы при --workers 1).
    """
    return await asyncio.to_thread(client.chat.completions.create, **kwargs)


def _build_user_context(user: User, db: Session) -> str:
    """Собирает контекст пользователя в текстовый блок для системного промпта."""
    today = datetime.now().date()
    lines = [
        f"=== СЕГОДНЯ: {today.strftime('%d.%m.%Y')} ({['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][today.weekday()]}) ===",
        f"\n=== ПРОФИЛЬ ===",
        f"Имя: {user.name}",
    ]
    if user.age:    lines.append(f"Возраст: {user.age} лет")
    if user.weight: lines.append(f"Вес: {user.weight} кг")
    if user.height: lines.append(f"Рост: {user.height} см")
    _level_map = {"beginner": "начинающий", "intermediate": "любитель", "advanced": "продвинутый"}
    _goal_map  = {"5k": "5 км", "10k": "10 км", "half_marathon": "полумарафон",
                  "marathon": "марафон", "fitness": "бег для здоровья"}
    if user.fitness_level:
        lines.append(f"Уровень: {_level_map.get(user.fitness_level, user.fitness_level)}")
    if user.running_goal:
        lines.append(f"Цель: {_goal_map.get(user.running_goal, user.running_goal)}")
    if user.weekly_km is not None:
        lines.append(f"Текущий объём: ~{user.weekly_km:.0f} км/нед")
    if user.training_days:
        lines.append(f"Дней для тренировок: {user.training_days} в неделю")

    # Активные цели
    goals = db.query(Goal).filter(Goal.user_id == user.id, Goal.is_active == True).all()
    if goals:
        lines.append("\n=== ЦЕЛИ ===")
        for g in goals:
            parts = [f"• {_goal_name(g.goal_type)}"]
            if g.target_distance_km: parts.append(f"{g.target_distance_km} км")
            if g.target_time_min:    parts.append(f"за {_fmt_time(g.target_time_min)}")
            if g.target_date:
                days_left = (g.target_date.date() - today).days
                parts.append(f"до {g.target_date.strftime('%d.%m.%Y')} (через {days_left} дн.)")
            lines.append(" ".join(parts))
    else:
        lines.append("\n=== ЦЕЛИ ===\nЦели не установлены.")

    # Недавно отменённые цели — явно помечаем как неактуальные, иначе модель может
    # достроить их статус из старых сообщений истории чата (см. system prompt выше).
    abandoned = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.is_abandoned == True)
        .order_by(Goal.updated_at.desc())
        .limit(3)
        .all()
    )
    if abandoned:
        lines.append("\n=== ОТМЕНЁННЫЕ ЦЕЛИ (неактуальны, не советуй по ним как по действующим) ===")
        for g in abandoned:
            parts = [f"• {_goal_name(g.goal_type)}"]
            if g.target_date:
                parts.append(f"(была на {g.target_date.strftime('%d.%m.%Y')})")
            parts.append("— отменена")
            lines.append(" ".join(parts))

    # История тренировок (все)
    recent = (
        db.query(Activity)
        .filter(Activity.user_id == user.id)
        .order_by(Activity.date.desc())
        .limit(60)
        .all()
    )
    _type_labels = {
        "run": "бег", "ride": "вело", "walk": "ходьба", "hike": "хайкинг",
        "swim": "плавание", "strength": "силовая", "workout": "тренировка", "other": "другое",
    }
    if recent:
        lines.append("\n=== ИСТОРИЯ ТРЕНИРОВОК ===")
        for a in recent:
            act_date = a.date.date() if hasattr(a.date, 'date') else a.date
            days_ago = (today - act_date).days
            ago_str  = "сегодня" if days_ago == 0 else f"{days_ago} дн. назад"
            pace_str = f"{_fmt_pace(a.pace_min_per_km)}/км" if a.pace_min_per_km else "—"
            hr_str   = f", ♥{a.avg_heart_rate}" if a.avg_heart_rate else ""
            max_hr   = f"(макс {a.max_heart_rate})" if a.max_heart_rate else ""
            elev     = f", ↑{a.elevation_gain:.0f}м" if a.elevation_gain else ""
            cad      = f", {a.avg_cadence}шаг/мин" if a.avg_cadence else ""
            type_label = _type_labels.get(a.activity_type or "run", a.activity_type or "бег")
            line = (
                f"• {a.date.strftime('%d.%m')} ({ago_str}) [{type_label}]: "
                f"{a.distance_km} км, {_fmt_time(a.duration_min)}, темп {pace_str}{hr_str}{max_hr}{elev}{cad}"
            )
            lines.append(line)

            # Сплиты по км (если есть)
            if a.splits and isinstance(a.splits, list) and len(a.splits) > 1:
                split_parts = []
                for s in a.splits:
                    km_pace = _fmt_pace(s["pace"]) if s.get("pace") else "—"
                    km_hr   = f"♥{s['avg_hr']}" if s.get("avg_hr") else ""
                    split_parts.append(f"К{s['km']}:{km_pace}{'/'+km_hr if km_hr else ''}")
                lines.append(f"  Сплиты: {', '.join(split_parts)}")

            # Круги (если есть)
            if a.laps and isinstance(a.laps, list) and len(a.laps) > 1:
                lap_parts = [
                    f"К{l['num']}:{l['dist_km']}км/{_fmt_pace(l['pace']) if l.get('pace') else '—'}"
                    for l in a.laps
                ]
                lines.append(f"  Круги: {', '.join(lap_parts)}")
    else:
        lines.append("\n=== ИСТОРИЯ ТРЕНИРОВОК ===\nТренировок пока нет.")

    # Статистика за 30 дней (только пробежки)
    since = datetime.now() - timedelta(days=30)
    month = db.query(Activity).filter(
        Activity.user_id == user.id,
        Activity.date >= since,
        Activity.activity_type == "run",
    ).all()
    if month:
        total_km  = sum(a.distance_km  for a in month)
        total_min = sum(a.duration_min for a in month)
        avg_pace  = total_min / total_km if total_km else 0
        weeks = 4
        lines.append(
            f"\n=== СТАТИСТИКА (30 дней) ===\n"
            f"Пробежек: {len(month)}, объём: {total_km:.1f} км (~{total_km/weeks:.1f} км/нед), "
            f"средний темп: {_fmt_pace(avg_pace)}/км"
        )
    else:
        lines.append("\n=== СТАТИСТИКА (30 дней) ===\nДанных нет.")

    # Текущий план — тренировки календарной недели, в которую попадает сегодня
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    workouts = db.query(Workout).filter(
        Workout.user_id == user.id,
        Workout.planned_date >= week_start,
        Workout.planned_date < week_start + timedelta(days=7),
    ).all()
    if workouts:
        lines.append(f"\n=== АКТИВНЫЙ ПЛАН (с {week_start.strftime('%d.%m')}) ===")
        day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        status_map = {"completed": "✓", "approximate": "≈", "unconfirmed": "✗", "none": "○"}
        for w in sorted(workouts, key=lambda x: (x.planned_date or datetime.min, x.day_of_week)):
            st   = status_map.get(w.completion_status or "none", "○")
            dist = f"{w.distance_km} км" if w.distance_km else ""
            date_prefix = w.planned_date.strftime('%d.%m') if w.planned_date else day_names[w.day_of_week]
            lines.append(f"  {date_prefix} {st} [{w.workout_type}] {w.description} {dist}".rstrip())
    else:
        lines.append("\n=== ПЛАН ===\nПлан не сформирован.")

    return "\n".join(lines)


def _build_history(messages: list[ChatMessage]) -> list[dict]:
    """Конвертирует историю чата в формат OpenAI messages.

    Только сообщения ПОЛЬЗОВАТЕЛЯ помечаются датой, когда они были написаны — без
    этого модель не может отличить «это было актуально тогда» от «это происходит
    сейчас» и путает старые даты/цели из истории с текущим положением дел.
    Ответы самого агента датой НЕ помечаются: иначе модель видит в истории свои
    же прошлые ответы с префиксом и начинает имитировать его в новых ответах —
    а на следующем вызове сюда добавляется ещё один префикс поверх уже
    сгенерированного моделью, и дата дублируется с каждым ходом (было замечено
    в проде: "[05.07.2026] [05.07.2026] [05.07.2026] ...").
    """
    result = []
    for m in messages[-20:]:  # последние 20 сообщений = ~контекст 10 ходов
        role = "user" if m.role == "user" else "assistant"
        if role == "user" and m.created_at:
            content = f"[{m.created_at.strftime('%d.%m.%Y')}] {m.content}"
        else:
            content = m.content
        result.append({"role": role, "content": content})
    return result


_DATE_PREFIX_RE = re.compile(r"^(?:\[\d{2}\.\d{2}\.\d{4}\]\s*)+")


def _strip_date_prefix(text: str) -> str:
    """Защитная зачистка — на случай, если модель всё же имитирует префикс [ДД.ММ.ГГГГ]
    из истории в своём ответе, убираем его перед сохранением/показом пользователю."""
    return _DATE_PREFIX_RE.sub("", text).strip()


# ── Публичные функции ─────────────────────────────────────────────────────────

async def chat_response(
    user_message: str,
    user: User,
    db: Session,
    history: list[ChatMessage],
    lang: str = "ru",
) -> str:
    """Генерирует ответ тренера на сообщение пользователя."""
    if _STUB_MODE:
        return _stub_chat(user_message, user)

    client = _make_client()
    lang_instruction = "Respond in English." if lang == "en" else "Отвечай на русском языке."
    context = _build_user_context(user, db)
    system  = f"{SYSTEM_PROMPT}\n{lang_instruction}\n\n{context}"
    messages = [{"role": "system", "content": system}]
    messages += _build_history(history)
    messages.append({"role": "user", "content": user_message})

    # Отдаём соединение обратно в пул на время ожидания DeepSeek (до 45с) —
    # без этого оно простаивало бы занятым весь запрос, и под несколько
    # одновременных AI-запросов пул мог исчерпаться, тормозя обычные быстрые
    # эндпоинты. Всё нужное из db уже прочитано выше в context/history — после
    # close() сессия остаётся рабочей, просто возьмёт новое соединение при
    # следующем обращении (вызывающий код чата коммитит перед этим await, так
    # что откатывать здесь нечего).
    db.close()

    try:
        resp = await _acreate(
            client,
            model="deepseek-chat",
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        return _strip_date_prefix(resp.choices[0].message.content.strip())
    except Exception as e:
        logger.error("DeepSeek chat error: %s", e)
        return "Извините, AI-тренер временно недоступен. Попробуйте позже."


def analyze_new_activity(activity, user: User, db: Session) -> str:
    """Синхронный автоанализ только что загруженной тренировки. Сохраняет сообщения в ChatMessage."""
    if _STUB_MODE:
        return ""

    client = _make_client()
    if not client:
        return ""

    context = _build_user_context(user, db)
    system = f"{SYSTEM_PROMPT}\nОтвечай на русском языке.\n\n{context}"

    type_map = {
        "run": "Пробежка", "ride": "Велотренировка", "walk": "Ходьба",
        "hike": "Хайкинг", "swim": "Плавание", "strength": "Силовая тренировка",
        "workout": "Тренировка", "other": "Активность",
    }
    type_name = type_map.get(activity.activity_type or "run", "Тренировка")
    pace_str = f"{_fmt_pace(activity.pace_min_per_km)}/км" if activity.pace_min_per_km else "—"
    hr_str = f"\n- ЧСС: {activity.avg_heart_rate} уд/мин" if activity.avg_heart_rate else ""
    elev_str = f"\n- Набор высоты: {activity.elevation_gain:.0f} м" if activity.elevation_gain else ""

    prompt = (
        f"Я только что загрузил(а) тренировку:\n\n"
        f"**{type_name}** {activity.date.strftime('%d.%m.%Y')}:\n"
        f"- Дистанция: {activity.distance_km} км\n"
        f"- Время: {_fmt_time(activity.duration_min)}\n"
        f"- Темп: {pace_str}{hr_str}{elev_str}\n\n"
        f"Разбери эту тренировку: как прошла, что хорошо, что можно улучшить, "
        f"как она вписывается в мою подготовку."
    )

    # Освобождаем соединение на время (синхронного, блокирующего) вызова DeepSeek —
    # этот код и так уже выполняется в фоновом потоке (BackgroundTasks), но сама
    # сессия БД всё равно держала бы слот пула все эти секунды без close().
    db.close()

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        ai_text = _strip_date_prefix(resp.choices[0].message.content.strip())
    except Exception as e:
        logger.error("DeepSeek analyze_new_activity error: %s", e)
        return ""

    db.add(ChatMessage(user_id=user.id, role="user", content=prompt, context_type="auto_analysis"))
    db.add(ChatMessage(user_id=user.id, role="ai", content=ai_text, context_type="auto_analysis"))
    db.commit()

    return ai_text


def analyze_workout_completion(workout, activity, user: User, db: Session) -> str:
    """Комментирует отметку тренировки из плана как выполненной — план vs факт.

    Вызывается только когда есть подтверждающая Activity (activity is not None) —
    без факта тренеру нечего разбирать, а комментировать «ничего не нашли» вслух
    от лица AI-агента не имеет смысла."""
    if _STUB_MODE:
        return ""

    client = _make_client()
    if not client:
        return ""

    context = _build_user_context(user, db)
    system = f"{SYSTEM_PROMPT}\nОтвечай на русском языке.\n\n{context}"

    plan_parts = [f"план — {workout.workout_type}, {workout.description}"]
    if workout.distance_km:
        plan_parts.append(f"{workout.distance_km} км")
    if workout.target_pace_min_km:
        plan_parts.append(f"целевой темп {_fmt_pace(workout.target_pace_min_km)}/км")

    pace_str = f"{_fmt_pace(activity.pace_min_per_km)}/км" if activity.pace_min_per_km else "—"
    fact = f"факт — {activity.distance_km} км, {_fmt_time(activity.duration_min)}, темп {pace_str}"

    status_label = STATUS_LABELS.get(workout.completion_status, workout.completion_status)

    prompt = (
        f"Я отметил(а) тренировку из плана как выполненную:\n\n"
        f"{', '.join(plan_parts)}\n{fact}\n"
        f"Статус по итогам сверки с планом: {status_label}\n\n"
        f"Прокомментируй, как прошла эта тренировка относительно плана — коротко, по делу, без критики."
    )

    # См. комментарий в analyze_new_activity — отдаём соединение в пул на время
    # блокирующего вызова DeepSeek.
    db.close()

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        ai_text = _strip_date_prefix(resp.choices[0].message.content.strip())
    except Exception as e:
        logger.error("DeepSeek analyze_workout_completion error: %s", e)
        return ""

    db.add(ChatMessage(user_id=user.id, role="user", content=prompt, context_type="workout_check"))
    db.add(ChatMessage(user_id=user.id, role="ai", content=ai_text, context_type="workout_check"))
    db.commit()

    return ai_text


def replace_upcoming_workouts(user_id: int, db: Session, workouts_data: list[dict], start: datetime) -> None:
    """Заменяет тренировки на ближайшие 7 дней начиная с `start`.

    Тренировки, по которым уже есть подтверждённый результат (completed/
    approximate), не трогаем — иначе перегенерация плана стирала бы реально
    пройденные тренировки текущей недели (раньше они просто "прятались" в
    деактивированном плане, а без плана-контейнера удаление было бы
    безвозвратным). Не закоммичено — коммитит вызывающий код.
    """
    start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)

    existing = db.query(Workout).filter(
        Workout.user_id == user_id,
        Workout.planned_date >= start_date,
        Workout.planned_date < end_date,
    ).all()
    protected_dates = set()
    for w in existing:
        if w.completion_status in ("completed", "approximate"):
            protected_dates.add(w.planned_date.date())
        else:
            db.delete(w)

    for i, w in enumerate(workouts_data):
        offset = w.get("day_of_week", i)
        planned = start_date + timedelta(days=offset)
        if planned.date() in protected_dates:
            continue
        db.add(Workout(
            user_id=user_id,
            day_of_week=planned.weekday(),
            planned_date=planned,
            workout_type=w.get("workout_type", "easy"),
            description=w.get("description", ""),
            distance_km=w.get("distance_km"),
            target_pace_min_km=w.get("target_pace_min_km"),
            duration_min=None,
            completion_status="none",
        ))


async def build_and_save_plan(user: User, db: Session) -> None:
    """Генерирует план через AI и сохраняет в БД. Используется из чата."""
    chat_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(30)
        .all()[::-1]
    )
    workouts_data = await generate_training_plan(user, db, chat_history)
    replace_upcoming_workouts(user.id, db, workouts_data, datetime.now())
    db.commit()


async def generate_training_plan(user: User, db: Session, chat_history: list[ChatMessage] | None = None) -> list[dict]:
    """
    Просит AI сгенерировать недельный план тренировок.
    Возвращает список словарей [{day_of_week, workout_type, description, distance_km, target_pace_min_km}].
    """
    if _STUB_MODE:
        return _stub_plan(user, db)

    client  = _make_client()
    context = _build_user_context(user, db)

    # Извлекаем предпочтения из последних 30 сообщений чата
    chat_context = ""
    if chat_history:
        relevant = [m for m in chat_history[-30:]
                    if any(w in m.content.lower() for w in
                           ["день", "дни", "понедельник","вторник","среда","четверг","пятница","суббота",
                            "воскресенье","пн","вт","ср","чт","пт","сб","вс","раз в","раза в",
                            "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
                            "times a week","days a week","prefer","хочу","могу","свободен"])]
        if relevant:
            chat_context = "\n=== ПРЕДПОЧТЕНИЯ ИЗ ЧАТА (учти при составлении плана) ===\n"
            chat_context += "\n".join(
                f"{'Спортсмен' if m.role == 'user' else 'Тренер'}: {m.content}"
                for m in relevant[-10:]
            )

    today_str = datetime.now().strftime('%d.%m.%Y')
    prompt = f"""{context}{chat_context}

Сегодня: {today_str}. Составь персональный план тренировок на ближайшие 7 дней \
(начиная с сегодняшнего дня) для этого спортсмена.
Верни ТОЛЬКО валидный JSON-массив из 7 объектов — по одному на каждый день, \
начиная с day_of_week=0 (сегодня), 1 (завтра), ..., 6 (через 6 дней).

Формат каждого объекта:
{{
  "day_of_week": 0,          // 0=сегодня, 1=завтра, ..., 6=через 6 дней
  "workout_type": "easy",    // easy | tempo | interval | long | recovery | rest
  "description": "...",      // описание тренировки на русском, 1-2 предложения
  "distance_km": 8.0,        // целевая дистанция (null для rest/recovery без бега)
  "target_pace_min_km": 5.5  // целевой темп мин/км (null для rest)
}}

Учитывай цели спортсмена, его текущий уровень и принцип 80/20. \
Расставь отдых и длинную пробежку разумно в течение недели.
Только JSON, без пояснений."""

    # См. комментарий в chat_response — освобождаем соединение на время ожидания
    # DeepSeek. Вызывающий код (generate_plan_ai/build_and_save_plan) нарочно не
    # оставляет здесь ничего незакоммиченного до этого await.
    db.close()

    try:
        resp = await _acreate(
            client,
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        # DeepSeek может обернуть массив в объект
        parsed = json.loads(raw)
        plan = parsed if isinstance(parsed, list) else next(
            (v for v in parsed.values() if isinstance(v, list)), []
        )
        return plan[:7]
    except Exception as e:
        logger.error("DeepSeek plan error: %s", e)
        return _stub_plan(user, db)


async def generate_insights(user: User, db: Session) -> list[str]:
    """Генерирует 2-4 коротких инсайта для дашборда."""
    if _STUB_MODE:
        return _stub_insights(user, db)

    client  = _make_client()
    context = _build_user_context(user, db)

    prompt = f"""{context}

На основе данных спортсмена дай 2-4 конкретных совета/наблюдения.
Верни ТОЛЬКО JSON-массив строк, например:
["Совет 1", "Совет 2"]
Каждый совет — одно предложение, конкретное, с цифрами где уместно."""

    # См. комментарий в chat_response — освобождаем соединение на время ожидания
    # DeepSeek. get_ai_dashboard() ничего не флашит перед этим await.
    db.close()

    try:
        resp = await _acreate(
            client,
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=400,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw    = resp.choices[0].message.content.strip()
        parsed = json.loads(raw)
        insights = parsed if isinstance(parsed, list) else next(
            (v for v in parsed.values() if isinstance(v, list)), []
        )
        return [str(i) for i in insights[:4]]
    except Exception as e:
        logger.error("DeepSeek insights error: %s", e)
        return _stub_insights(user, db)


# ── Заглушки (пока нет ключа) ─────────────────────────────────────────────────

def _stub_chat(message: str, user: User) -> str:
    msg = message.lower()
    if any(w in msg for w in ["план", "тренировк", "неделя"]):
        return ("🏃 Сформирую персональный план тренировок с учётом ваших целей! "
                "Нажмите «Сформировать» в блоке плана тренировок. "
                "_(AI-агент будет активирован после добавления ключа DeepSeek)_")
    if any(w in msg for w in ["питание", "еда", "гель", "углевод"]):
        return ("🍌 Основные принципы питания бегуна: за 2ч до старта — сложные углеводы "
                "(овсянка, рис). На дистанции >90 мин — гели каждые 40 мин + электролиты. "
                "После — белок+углеводы в течение 30 мин.")
    if any(w in msg for w in ["боль", "травм", "колен", "голен"]):
        return ("🩺 При болях важно: 1) снизить нагрузку на 50%, 2) проверить износ кроссовок "
                "(менять каждые 700-800 км), 3) добавить упражнения на укрепление кора. "
                "При острой боли — обратитесь к врачу.")
    if any(w in msg for w in ["темп", "скорост", "быстр"]):
        return ("⚡ Для улучшения темпа: 80% пробежек в лёгкой зоне (можете говорить), "
                "1 темповая тренировка в неделю (20-40 мин в комфортно-тяжёлом темпе), "
                "1 интервальная (6×800м с отдыхом 90 сек).")
    return (f"👋 Привет, {user.name}! Я AI-тренер по бегу. "
            "Спросите меня о плане тренировок, темпе, питании или технике. "
            "_(Полный AI доступен после подключения DeepSeek API)_")


def _stub_plan(user: User, db: Session) -> list[dict]:
    goals = db.query(Goal).filter(Goal.user_id == user.id, Goal.is_active == True).all()
    goal_type = goals[0].goal_type if goals else "half_marathon"

    plans = {
        "half_marathon": [
            {"day_of_week":0,"workout_type":"easy",     "description":"Лёгкий бег в разговорном темпе",            "distance_km":6,  "target_pace_min_km":5.8},
            {"day_of_week":1,"workout_type":"rest",      "description":"Отдых или лёгкая растяжка",                "distance_km":None,"target_pace_min_km":None},
            {"day_of_week":2,"workout_type":"tempo",     "description":"Темповая пробежка: 2км разм + 6км темп + 2км заминка","distance_km":10, "target_pace_min_km":5.1},
            {"day_of_week":3,"workout_type":"easy",      "description":"Восстановительный бег, очень лёгкий темп", "distance_km":5,  "target_pace_min_km":6.0},
            {"day_of_week":4,"workout_type":"interval",  "description":"Интервалы 6×800м, отдых 90 сек между",     "distance_km":8,  "target_pace_min_km":4.5},
            {"day_of_week":5,"workout_type":"long",      "description":"Длинная пробежка в лёгком темпе",          "distance_km":16, "target_pace_min_km":5.9},
            {"day_of_week":6,"workout_type":"recovery",  "description":"Активное восстановление: ходьба или йога", "distance_km":None,"target_pace_min_km":None},
        ],
        "full_marathon": [
            {"day_of_week":0,"workout_type":"easy",    "description":"Лёгкий бег",                              "distance_km":8,  "target_pace_min_km":5.8},
            {"day_of_week":1,"workout_type":"tempo",   "description":"Темповая 10 км",                         "distance_km":10, "target_pace_min_km":5.0},
            {"day_of_week":2,"workout_type":"easy",    "description":"Восстановление 6 км",                    "distance_km":6,  "target_pace_min_km":6.1},
            {"day_of_week":3,"workout_type":"interval","description":"Интервалы 8×800м",                       "distance_km":10, "target_pace_min_km":4.4},
            {"day_of_week":4,"workout_type":"easy",    "description":"Лёгкий бег 7 км",                        "distance_km":7,  "target_pace_min_km":5.9},
            {"day_of_week":5,"workout_type":"long",    "description":"Длинная пробежка",                       "distance_km":26, "target_pace_min_km":5.8},
            {"day_of_week":6,"workout_type":"rest",    "description":"Полный отдых",                           "distance_km":None,"target_pace_min_km":None},
        ],
        "default": [
            {"day_of_week":0,"workout_type":"easy",    "description":"Лёгкий бег 5 км",                        "distance_km":5,  "target_pace_min_km":6.0},
            {"day_of_week":1,"workout_type":"rest",    "description":"Отдых",                                  "distance_km":None,"target_pace_min_km":None},
            {"day_of_week":2,"workout_type":"tempo",   "description":"Темповая 6 км",                         "distance_km":6,  "target_pace_min_km":5.2},
            {"day_of_week":3,"workout_type":"easy",    "description":"Восстановление 5 км",                   "distance_km":5,  "target_pace_min_km":6.2},
            {"day_of_week":4,"workout_type":"interval","description":"Интервалы 5×400м",                      "distance_km":5,  "target_pace_min_km":4.6},
            {"day_of_week":5,"workout_type":"long",    "description":"Длинная пробежка",                      "distance_km":10, "target_pace_min_km":6.0},
            {"day_of_week":6,"workout_type":"rest",    "description":"Отдых",                                  "distance_km":None,"target_pace_min_km":None},
        ],
    }
    return plans.get(goal_type, plans["default"])


def _stub_insights(user: User, db: Session) -> list[str]:
    since = datetime.now() - timedelta(days=30)
    activities = db.query(Activity).filter(
        Activity.user_id == user.id, Activity.date >= since
    ).all()

    insights = []
    count = len(activities)
    total_km = sum(a.distance_km for a in activities)

    if count == 0:
        return ["✨ Добавьте первые пробежки, чтобы получать персональные советы!"]

    if count < 8:
        insights.append(f"📅 За месяц {count} пробежек — для прогресса стремитесь к 12-16 в месяц")
    else:
        insights.append(f"🔥 Отличная регулярность: {count} пробежек за месяц!")

    weekly = total_km / 4
    if weekly < 20:
        insights.append(f"📈 Недельный объём ~{weekly:.0f} км — постепенно увеличивайте на 10% в неделю")
    elif weekly > 60:
        insights.append(f"⚠️ Объём {weekly:.0f} км/нед — следите за восстановлением, добавьте лёгкие дни")
    else:
        insights.append(f"✅ Хороший объём: ~{weekly:.0f} км в неделю")

    paces = [a.pace_min_per_km for a in activities if a.pace_min_per_km]
    if paces:
        avg = sum(paces) / len(paces)
        insights.append(f"⏱ Средний темп за месяц: {_fmt_pace(avg)}/км — "
                        f"{'добавьте интервальные тренировки для скорости' if avg > 6 else 'хороший темп!'}")

    return insights[:4]


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _goal_name(t: str) -> str:
    return {"half_marathon":"Полумарафон","full_marathon":"Марафон",
            "10k":"10 км","5k":"5 км","custom":"Своя цель"}.get(t, t)

def _fmt_time(minutes: float) -> str:
    h = int(minutes // 60); m = int(minutes % 60)
    return f"{h}ч {m}м" if h else f"{m}м"

def _fmt_pace(pace: float) -> str:
    m = int(pace); s = round((pace - m) * 60)
    return f"{m}:{s:02d}"
