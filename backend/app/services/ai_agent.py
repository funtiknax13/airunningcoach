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
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import httpx
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models import User, Activity, Goal, Workout, ChatMessage, PlanJob
from app.services.workout_verification import STATUS_LABELS

logger = logging.getLogger(__name__)

# Провайдеры AI и режим-заглушка определены ниже (см. _providers / _chat / _STUB_MODE).

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
- Про пересборку плана — смотри блок «ПЛАН ТОЛЬКО ЧТО ПЕРЕСОБРАН» / «ПЛАН НЕ ПЕРЕСОБИРАЛСЯ» \
  в конце контекста ниже и следуй ему буквально. Никогда не утверждай, что обновила план, \
  если это не подтверждено этим блоком — ты не можешь изменить план просто фактом ответа.
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


# ── Провайдеры AI: Groq (основной) → DeepSeek (на подхвате) ──────────────────
# Оба OpenAI-совместимые (отличаются base_url / ключом / моделью). При 429 или
# сбое провайдера прозрачно уходим к следующему; упавший ставим на кулдаун, чтобы
# не дёргать его на каждом запросе (особенно когда у Groq кончились токены за сутки).

def _providers() -> list[dict]:
    """Список включённых провайдеров по приоритету. Включён = задан ключ."""
    out: list[dict] = []
    if settings.GROQ_API_KEY:
        out.append({"name": "groq", "base_url": settings.GROQ_BASE_URL,
                    "api_key": settings.GROQ_API_KEY, "model": settings.GROQ_MODEL,
                    "proxy": settings.GROQ_PROXY or None})
    dk = settings.DEEPSEEK_API_KEY
    if dk and dk != "your-deepseek-api-key-here":
        out.append({"name": "deepseek", "base_url": settings.DEEPSEEK_BASE_URL,
                    "api_key": dk, "model": settings.DEEPSEEK_MODEL})
    return out


# Заглушка (стаб), когда не настроен НИ ОДИН провайдер.
_STUB_MODE = len(_providers()) == 0

_clients: dict[str, OpenAI] = {}


def _client_for(p: dict) -> OpenAI:
    c = _clients.get(p["name"])
    if c is None:
        kwargs = dict(
            api_key=p["api_key"], base_url=p["base_url"],
            timeout=45.0,     # дефолт OpenAI = 600 сек; зависший запрос не должен морозить воркер
            max_retries=1,
        )
        # Прокси только для провайдера, у которого он задан (Groq в РФ обходит гео-блок).
        if p.get("proxy"):
            kwargs["http_client"] = httpx.Client(proxy=p["proxy"], timeout=45.0)
        c = OpenAI(**kwargs)
        _clients[p["name"]] = c
    return c


# Кулдаун упавшего провайдера — в памяти, свой на каждый воркер.
#
# 429 у Groq почти всегда означает TPM/RPM-лимит (сбрасывается за секунды-десятки
# секунд), а не дневной — но сам ответ Groq обычно прямо говорит, сколько ждать
# ("...Please try again in 3.25s...", + заголовок Retry-After), так что достаём
# реальное время оттуда вместо того, чтобы гадать. Дневной/месячный лимит
# встречается редко и опознаётся по тексту ошибки — для него бэкофф подольше.
_COOLDOWN_RATE_DEFAULT = 60    # 429 без опознанного времени ожидания — короткий бэкофф
_COOLDOWN_RATE_DAILY   = 900   # 429 с явным упоминанием дневного/месячного лимита
_COOLDOWN_ERR          = 60    # прочие сбои (не rate-limit) — коротко
_cooldown_until: dict[str, float] = {}

_RETRY_AFTER_RE = re.compile(r"try again in\s+([\d.]+)\s*s", re.IGNORECASE)
_DAILY_LIMIT_RE = re.compile(r"per day|tokens per day|requests per day|\bTPD\b|\bRPD\b", re.IGNORECASE)


def _in_cooldown(name: str) -> bool:
    return time.time() < _cooldown_until.get(name, 0.0)


def _is_rate_limit(e: Exception) -> bool:
    return getattr(e, "status_code", None) == 429 or "RateLimit" in type(e).__name__ or " 429" in f" {e}"


def _rate_limit_cooldown(e: Exception) -> float:
    """Сколько ждать после 429. Порядок: заголовок Retry-After → "try again in Xs"
    в тексте ошибки → явное упоминание дневного/месячного лимита (подольше) →
    короткий дефолт (обычно это и есть TPM/RPM, а не дневной лимит)."""
    response = getattr(e, "response", None)
    header_val = response.headers.get("retry-after") if response is not None else None
    if header_val:
        try:
            return max(1.0, float(header_val))
        except ValueError:
            pass
    msg = str(e)
    m = _RETRY_AFTER_RE.search(msg)
    if m:
        try:
            return max(1.0, float(m.group(1)))
        except ValueError:
            pass
    if _DAILY_LIMIT_RE.search(msg):
        return _COOLDOWN_RATE_DAILY
    return _COOLDOWN_RATE_DEFAULT


def _set_cooldown(name: str, e: Exception) -> None:
    cooldown = _rate_limit_cooldown(e) if _is_rate_limit(e) else _COOLDOWN_ERR
    _cooldown_until[name] = time.time() + cooldown
    logger.warning("Провайдер '%s' в кулдауне на %.0fс", name, cooldown)


async def _acreate(client: OpenAI, **kwargs):
    """Блокирующий вызов провайдера в отдельном потоке — не морозит asyncio event loop.

    Sync-клиент OpenAI делает обычный сетевой запрос, который в `async def`-эндпоинте
    блокировал бы весь event loop (а значит и все остальные запросы при --workers 1).
    """
    return await asyncio.to_thread(client.chat.completions.create, **kwargs)


def _ordered_providers() -> list[dict]:
    """Провайдеры по приоритету; в кулдауне — в самый конец (пробуем как крайний
    вариант, а не пропускаем совсем, чтобы не остаться без ответа)."""
    ps = _providers()
    return [p for p in ps if not _in_cooldown(p["name"])] + [p for p in ps if _in_cooldown(p["name"])]


def _chat_kwargs(p, messages, max_tokens, temperature, response_format):
    kwargs = dict(model=p["model"], messages=messages, max_tokens=max_tokens, temperature=temperature)
    if response_format is not None:
        kwargs["response_format"] = response_format
    return kwargs


async def _chat(messages: list[dict], max_tokens: int, temperature: float,
                response_format: dict | None = None):
    """Асинхронный чат-запрос с failover Groq→DeepSeek. При сбое провайдера — к
    следующему; упавший уходит в кулдаун. Все упали → пробрасываем (вызывающий
    код уходит в свой stub)."""
    last_exc: Exception | None = None
    for p in _ordered_providers():
        try:
            return await _acreate(_client_for(p), **_chat_kwargs(p, messages, max_tokens, temperature, response_format))
        except Exception as e:
            last_exc = e
            _set_cooldown(p["name"], e)
            logger.warning("AI провайдер '%s' упал (%s) — пробуем следующий", p["name"], e)
    raise last_exc if last_exc else RuntimeError("нет настроенных AI-провайдеров")


def _chat_sync(messages: list[dict], max_tokens: int, temperature: float,
               response_format: dict | None = None):
    """Синхронный вариант _chat — для фоновых задач (analyze_*), которые сами
    выполняются в отдельном потоке и не могут await'ить."""
    last_exc: Exception | None = None
    for p in _ordered_providers():
        try:
            return _client_for(p).chat.completions.create(**_chat_kwargs(p, messages, max_tokens, temperature, response_format))
        except Exception as e:
            last_exc = e
            _set_cooldown(p["name"], e)
            logger.warning("AI провайдер '%s' упал (%s) — пробуем следующий", p["name"], e)
    raise last_exc if last_exc else RuntimeError("нет настроенных AI-провайдеров")


def _build_user_context(user: User, db: Session) -> str:
    """Собирает контекст пользователя в текстовый блок для системного промпта."""
    try:
        today = datetime.now(ZoneInfo(user.timezone)).date() if user.timezone else datetime.now().date()
    except Exception:
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
            act_dt = a.date
            if user.timezone and act_dt.tzinfo is not None:
                try:
                    act_dt = act_dt.astimezone(ZoneInfo(user.timezone))
                except Exception:
                    pass
            act_date = act_dt.date() if hasattr(act_dt, 'date') else act_dt
            days_ago = (today - act_date).days
            ago_str  = "сегодня" if days_ago == 0 else f"{days_ago} дн. назад"
            pace_str = f"{_fmt_pace(a.pace_min_per_km)}/км" if a.pace_min_per_km else "—"
            hr_str   = f", ♥{a.avg_heart_rate}" if a.avg_heart_rate else ""
            max_hr   = f"(макс {a.max_heart_rate})" if a.max_heart_rate else ""
            elev     = f", ↑{a.elevation_gain:.0f}м" if a.elevation_gain else ""
            cad      = f", {a.avg_cadence}шаг/мин" if a.avg_cadence else ""
            type_label = _type_labels.get(a.activity_type or "run", a.activity_type or "бег")
            line = (
                f"• {act_dt.strftime('%d.%m')} ({ago_str}) [{type_label}]: "
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

    # Текущий план — от "сегодня минус 7 дней" и без верхней границы, а НЕ строгая
    # календарная неделя пн-вс. replace_upcoming_workouts() пишет план скользящим
    # окном "7 дней от момента пересборки" (может начаться в среду, четверг —
    # где угодно), а не с понедельника. Если тут фильтровать по календарной
    # неделе, часть реально активного плана (например, следующие пн-вт, если
    # план пересобрали в среду) молча выпадала из контекста модели — она "не
    # видела" актуальный план и путала бегуна с устаревшими данными.
    plan_window_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    workouts = db.query(Workout).filter(
        Workout.user_id == user.id,
        Workout.planned_date >= plan_window_start,
    ).order_by(Workout.planned_date).all()
    if workouts:
        lines.append("\n=== ПЛАН (последние 7 дней + все запланированные вперёд) ===")
        day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        status_map = {"completed": "✓", "approximate": "≈", "unconfirmed": "✗", "none": "○"}
        for w in workouts:
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
    plan_just_regenerated: bool = False,
) -> str:
    """Генерирует ответ тренера на сообщение пользователя.

    plan_just_regenerated: True, если ДО этого вызова план уже реально пересобран
    и сохранён (см. chat.py — проверка и пересборка происходят раньше, чем этот
    ответ генерируется). Без этого модель по своей собственной оценке "пользователь
    просит план" утверждала "план обновлён", даже когда код это не подтверждал
    (отдельная, гораздо более грубая проверка по ключевым словам) — реального
    обновления не происходило, а пользователь читал ложное подтверждение."""
    if _STUB_MODE:
        return _stub_chat(user_message, user)

    lang_instruction = "Respond in English." if lang == "en" else "Отвечай на русском языке."
    context = _build_user_context(user, db)
    plan_status = (
        "\n\n=== ПЛАН ТОЛЬКО ЧТО ПЕРЕСОБРАН ===\nПлан уже пересчитан и сохранён прямо перед этим ответом — "
        "можешь уверенно сказать, что он обновлён и появится во вкладке «Тренировки»."
        if plan_just_regenerated else
        "\n\n=== ПЛАН НЕ ПЕРЕСОБИРАЛСЯ В ЭТОМ СООБЩЕНИИ ===\nЕсли похоже, что пользователь просит "
        "изменить план — НЕ утверждай, что уже изменила его: это не так. Прямо скажи, что для "
        "пересборки нужна явная фраза («обнови план», «пересобери план», «составь план» и т.п.) "
        "или кнопка «Создать план» на вкладке «Тренировки»."
    )
    system  = f"{SYSTEM_PROMPT}\n{lang_instruction}\n\n{context}{plan_status}"
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
        resp = await _chat(messages=messages, max_tokens=800, temperature=0.7)
        return _strip_date_prefix(resp.choices[0].message.content.strip())
    except Exception as e:
        logger.error("DeepSeek chat error: %s", e)
        return "Извините, AI-тренер временно недоступен. Попробуйте позже."


_UNAVAILABLE_MSG = "Извините, AI-тренер временно недоступен. Попробуйте позже."


def _save_unavailable_notice(user: User, db: Session, context_type: str) -> str:
    """Пишет сообщение-заглушку, когда анализ недоступен/упал.

    Клиент показывает бейдж "есть новое сообщение" сразу по факту постановки
    анализа в фон (см. ai_analysis_pending), ещё до того, как этот код
    отработает — если тут молча вернуть "", бейдж загорится, а сообщение
    никогда не появится. Раньше так и было (пользователь сообщил о тренировке
    "ходьба", по которой пришло уведомление, но не пришло сообщение)."""
    db.add(ChatMessage(user_id=user.id, role="ai", content=_UNAVAILABLE_MSG, context_type=context_type, read=False))
    db.commit()
    return _UNAVAILABLE_MSG


def analyze_new_activity(activity_id: int, user_id: int) -> str:
    """Синхронный автоанализ только что загруженной тренировки. Сохраняет сообщения в ChatMessage.

    Открывает СВОЮ собственную сессию БД, а не переиспользует сессию исходного HTTP-запроса:
    это background task, который Starlette выполняет в отдельном потоке из пула (run_in_threadpool),
    а SQLAlchemy Session не потокобезопасна. Из-за этого сообщение — даже запасное
    "AI недоступен" — иногда не сохранялось вообще: реальные логи показали месяц загруженных
    тренировок без единого сообщения от тренера."""
    db = SessionLocal()
    try:
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not activity or not user:
            return ""

        if _STUB_MODE:
            return _save_unavailable_notice(user, db, "auto_analysis")

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
        # сессия своя и используется только этим потоком от начала до конца, поэтому
        # close() + неявное переоткрытие ниже безопасны (в отличие от версии, где сессия
        # приходила из другого потока).
        db.close()

        try:
            resp = _chat_sync(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.7,
            )
            ai_text = _strip_date_prefix(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.error("AI analyze_new_activity error: %s", e)
            return _save_unavailable_notice(user, db, "auto_analysis")

        db.add(ChatMessage(user_id=user.id, role="user", content=prompt, context_type="auto_analysis"))
        db.add(ChatMessage(user_id=user.id, role="ai", content=ai_text, context_type="auto_analysis", read=False))
        db.commit()

        return ai_text
    finally:
        db.close()


def analyze_workout_completion(workout_id: int, activity_id: int, user_id: int) -> str:
    """Комментирует отметку тренировки из плана как выполненной — план vs факт.

    Вызывается только когда есть подтверждающая Activity (activity is not None) —
    без факта тренеру нечего разбирать, а комментировать «ничего не нашли» вслух
    от лица AI-агента не имеет смысла.

    Своя сессия БД — см. комментарий в analyze_new_activity про потокобезопасность."""
    db = SessionLocal()
    try:
        workout = db.query(Workout).filter(Workout.id == workout_id).first()
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not workout or not activity or not user:
            return ""

        if _STUB_MODE:
            return _save_unavailable_notice(user, db, "workout_check")

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
            resp = _chat_sync(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.7,
            )
            ai_text = _strip_date_prefix(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.error("AI analyze_workout_completion error: %s", e)
            return _save_unavailable_notice(user, db, "workout_check")

        db.add(ChatMessage(user_id=user.id, role="user", content=prompt, context_type="workout_check"))
        db.add(ChatMessage(user_id=user.id, role="ai", content=ai_text, context_type="workout_check", read=False))
        db.commit()

        _check_ai_verdict_against_code(workout, activity)

        return ai_text
    finally:
        db.close()


def _check_ai_verdict_against_code(workout: Workout, activity: Activity) -> None:
    """Скрытая сверка: независимый от кода вердикт ИИ по тем же фактам плана/факта,
    БЕЗ подсказки уже вычисленного workout.completion_status — иначе модель просто
    повторит то, что ей сказали, и сверка ничего не покажет. Никогда не показывается
    пользователю — только лог, как сигнал для калибровки (тот же принцип, что и
    ручная калибровка детектора интервалов по реальным файлам в этой сессии).

    Сбой здесь не должен испортить уже сохранённый пользователю ответ тренера —
    свой изолированный try/except, никогда не поднимает исключение наружу и не
    трогает _save_unavailable_notice (та привязана к видимому сообщению)."""
    try:
        plan_parts = [f"план — {workout.workout_type}, {workout.description}"]
        if workout.distance_km:
            plan_parts.append(f"{workout.distance_km} км")
        if workout.target_pace_min_km:
            plan_parts.append(f"целевой темп {_fmt_pace(workout.target_pace_min_km)}/км")
        if workout.plan_structure:
            plan_parts.append(f"структура: {json.dumps(workout.plan_structure, ensure_ascii=False)}")

        pace_str = f"{_fmt_pace(activity.pace_min_per_km)}/км" if activity.pace_min_per_km else "—"
        fact_parts = [f"факт — {activity.distance_km} км, {_fmt_time(activity.duration_min)}, темп {pace_str}"]
        analysis = activity.analysis if isinstance(activity.analysis, dict) else None
        intervals = analysis.get("intervals") if analysis else None
        if intervals and intervals.get("kind") == "intervals":
            reps = intervals.get("reps") or []
            if reps:
                avg_pace = sum(r.get("pace_min_km") or 0 for r in reps) / len(reps)
                fact_parts.append(f"обнаружено интервалов: {len(reps)}, средний темп повтора {_fmt_pace(avg_pace)}/км")

        prompt = (
            f"{', '.join(plan_parts)}\n{'; '.join(fact_parts)}\n\n"
            'Оцени, выполнена ли эта тренировка относительно плана. Ответь строго JSON вида '
            '{"verdict": "completed"|"approximate"|"unconfirmed", "reason": "краткая причина"}. '
            "completed — уложились в план (~7% допуска по дистанции/темпу), "
            "approximate — частично (до ~30% отклонения), unconfirmed — существенно разошлось с планом."
        )
        resp = _chat_sync(
            messages=[
                {"role": "system", "content": "Ты оцениваешь соответствие пробежки плану тренировки. Отвечай только JSON, без пояснений вне JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        ai_verdict = parsed.get("verdict")
        if ai_verdict not in ("completed", "approximate", "unconfirmed"):
            return
        if ai_verdict != workout.completion_status:
            logger.warning(
                "AI/code verdict mismatch: workout_id=%s code=%s ai=%s reason=%s",
                workout.id, workout.completion_status, ai_verdict, parsed.get("reason"),
            )
    except Exception as e:
        logger.debug("AI verdict cross-check skipped (workout_id=%s): %s", workout.id, e)


def _plan_item_schema(desc_rule: str) -> str:
    """Общий фрагмент промпта — формат JSON одного дня плана. Раньше был продублирован
    в generate_training_plan и _gen_plan_chunk по отдельности и рисковал разъехаться —
    теперь оба места собирают промпт из одного источника."""
    return f"""Формат объекта:
{{
  "workout_type": "easy",    // easy | tempo | interval | long | recovery | rest
  "description": "...",      // {desc_rule}
  "distance_km": 8.0,        // целевая дистанция (null для rest)
  "target_pace_min_km": 5.5, // целевой темп мин/км (null для rest)
  "plan_structure": null     // структура интервалов — см. правило ниже
}}

plan_structure: null для ВСЕХ типов, КРОМЕ interval — там вместо null дай объект вида
{{"warmup_km": 2.0, "main": [{{"reps": 6, "distance_m": 1000, "target_pace_min_km": 4.2, "recovery_m": 400, "recovery_pace_min_km": 6.0}}], "cooldown_km": 1.5}}
(несколько блоков в "main", если тренировка комбинирует разные отрезки — например пирамида
200/400/800/400/200). Не выдумывай структуру для easy/tempo/long/recovery/rest — там всегда null."""


def _validate_plan_structure(ps) -> Optional[dict]:
    """Защита от мусора в structured-поле от модели: сохраняем, только если форма
    похожа на ожидаемую, иначе тихо отбрасываем (тренировка остаётся плоской, как
    раньше) — не даём кривому JSON сломать рендер плана у пользователя."""
    if not isinstance(ps, dict):
        return None
    main = ps.get("main")
    if not isinstance(main, list) or not main:
        return None
    for block in main:
        if not isinstance(block, dict) or "reps" not in block or "distance_m" not in block:
            return None
    return ps


def replace_upcoming_workouts(
    user_id: int, db: Session, workouts_data: list[dict], start: datetime,
    horizon_days: int = 7,
) -> None:
    """Заменяет тренировки в окне [start, start+horizon_days) на новые.

    horizon_days задаёт горизонт плана (7 — неделя, 28 — месяц, 84 — 3 месяца).
    Элементы workouts_data идут по порядку: элемент i = день (start + i дней) —
    дату берём по индексу, а не по полю day_of_week (для длинных планов модель
    не должна вести сквозной счётчик дней, только выдавать дни по порядку).

    Тренировки с подтверждённым результатом (completed/approximate) не трогаем —
    иначе перегенерация стирала бы реально пройденные дни. Не коммитит.
    """
    # Защита от разрушительного "пустого" плана: если генерация вернула пусто —
    # НЕ трогаем существующие тренировки, иначе удалим текущий план (в т.ч.
    # сегодняшний отдых) и не добавим ничего. Пустой план не должен ничего стирать.
    if not workouts_data:
        logger.warning("replace_upcoming_workouts: пустой план — пропускаю, оставляю текущие тренировки")
        return

    start_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=horizon_days)

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

    for i, w in enumerate(workouts_data[:horizon_days]):
        planned = start_date + timedelta(days=i)
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
            plan_structure=_validate_plan_structure(w.get("plan_structure")),
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
    # Локальный "сегодня" бегуна, снятый до naive перед сравнением с planned_date
    # (наивная колонка) — см. комментарий в routers/training.py у второго вызова.
    # План начинается с завтра: модель не знает, сколько от сегодня уже прошло,
    # и может поставить полноценную тренировку на день, который наполовину позади.
    try:
        now_local = datetime.now(ZoneInfo(user.timezone)) if user.timezone else datetime.now()
    except Exception:
        now_local = datetime.now()
    start = now_local.replace(tzinfo=None) + timedelta(days=1)
    replace_upcoming_workouts(user.id, db, workouts_data, start)
    db.commit()


def _extract_plan_list(parsed) -> list[dict]:
    """Достаёт список дней плана из ответа DeepSeek, устойчиво к форме обёртки.

    response_format=json_object запрещает массив на верхнем уровне, поэтому модель
    оборачивает план по-разному:
      • {"plan": [ {...}, ... ]}          — массив в значении (любой ключ)
      • {"day_0": {...}, "day_1": {...}}  — дни как ключи объекта
      • {"day_of_week": 0, ...}           — один плоский объект-день (мусорный ответ)
    Первые две формы — валидны, возвращаем список. Одиночный плоский объект считаем
    негодным (нужна неделя, а не один день) — вернём [], вызывающий код уйдёт в stub.
    """
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
        day_objs = [v for v in parsed.values()
                    if isinstance(v, dict) and ("workout_type" in v or "day_of_week" in v)]
        if len(day_objs) >= 2:
            return day_objs
    return []


def _plan_chat_prefs(chat_history: list[ChatMessage] | None) -> str:
    """Вытаскивает из истории чата предпочтения по расписанию (дни/частота), чтобы
    учесть их при составлении плана. Возвращает готовый блок или пустую строку."""
    if not chat_history:
        return ""
    relevant = [m for m in chat_history[-30:]
                if any(w in m.content.lower() for w in
                       ["день", "дни", "понедельник","вторник","среда","четверг","пятница","суббота",
                        "воскресенье","пн","вт","ср","чт","пт","сб","вс","раз в","раза в",
                        "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
                        "times a week","days a week","prefer","хочу","могу","свободен"])]
    if not relevant:
        return ""
    body = "\n".join(
        f"{'Спортсмен' if m.role == 'user' else 'Тренер'}: {m.content}"
        for m in relevant[-10:]
    )
    return "\n=== ПРЕДПОЧТЕНИЯ ИЗ ЧАТА (учти при составлении плана) ===\n" + body


async def _gen_plan_chunk(
    context: str, chat_context: str, total_weeks: int,
    week_from: int, week_to: int, start_index: int, n: int,
    prev_tail: list[dict], stub_week: list[dict], chunk_start_date: datetime,
) -> list[dict]:
    """Один быстрый вызов DeepSeek на кусок плана (n дней недель week_from..week_to).

    Периодизация задаётся по ВСЕМУ блоку (total_weeks), а непрерывность — через
    хвост предыдущего куска. Пустой/сбойный ответ → тайлим недельный стаб (кусок
    никогда не пустой, чтобы не порвать сборку). Без обращения к БД (context уже
    собран заранее) — безопасно вызывать из фоновой задачи."""
    def _stub(): return [dict(stub_week[(start_index + i) % 7]) for i in range(n)]
    if _STUB_MODE:
        return _stub()
    prev_txt = ""
    if prev_tail:
        prev_txt = ("Предыдущие дни (продолжай логично отсюда, не обрывай прогрессию): "
                    + "; ".join(f"{w.get('workout_type')} {w.get('distance_km') or ''}".strip()
                                for w in prev_tail))
    _WD = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
    chunk_start_str = f"{chunk_start_date.strftime('%d.%m.%Y')} ({_WD[chunk_start_date.weekday()]})"
    prompt = f"""{context}{chat_context}

Ты составляешь ДЛИННЫЙ план на {total_weeks} недель с периодизацией по всему блоку: \
чередуй развивающие недели с разгрузочными (каждая 3-4-я неделя легче на ~20-30%), \
наращивай недельный объём не быстрее ~10% и откатывай в разгрузочные недели, 1 длинная \
пробежка в неделю с плавным ростом, правило 80/20, подводка (taper) перед целевым стартом.
Сейчас верни ТОЛЬКО дни для недель {week_from}–{week_to} этого блока — ровно {n} объектов \
ПО ПОРЯДКУ (элемент 0 = {chunk_start_str}, ..., {n - 1} = последний день куска). {prev_txt}

{_plan_item_schema("коротко 3-8 слов")}

Верни строго {{"plan": [ ... {n} объектов ... ]}}. Только JSON, без пояснений."""
    try:
        resp = await _chat(
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            max_tokens=min(4000, max(600, n * 75)),
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        plan = _extract_plan_list(json.loads(resp.choices[0].message.content.strip()))
    except Exception as e:
        logger.error("AI plan chunk error (weeks %s-%s): %s", week_from, week_to, e)
        plan = []
    if not plan:
        return _stub()
    # добиваем длину куска стабом, если модель вернула меньше n
    for i in range(len(plan), n):
        plan.append(dict(stub_week[(start_index + i) % 7]))
    return plan[:n]


async def generate_plan_chunked(
    context: str, chat_context: str, stub_week: list[dict], days: int, start_date: datetime,
) -> list[dict]:
    """Собирает длинный план из 2-недельных кусков (каждый — быстрый вызов в пределах
    таймаута). Возвращает ровно `days` дней по порядку. Без БД — только awaits."""
    CHUNK = 14
    total_weeks = (days + 6) // 7
    out: list[dict] = []
    while len(out) < days:
        n = min(CHUNK, days - len(out))
        week_from = len(out) // 7 + 1
        week_to = (len(out) + n - 1) // 7 + 1
        chunk = await _gen_plan_chunk(
            context, chat_context, total_weeks, week_from, week_to,
            len(out), n, out[-3:], stub_week, start_date + timedelta(days=len(out)),
        )
        out.extend(chunk[:n])
    return out[:days]


async def run_plan_job(user_id: int, weeks: int, job_id: int, include_today: bool = False) -> None:
    """Фоновая генерация длинного плана. Открывает свою сессию БД (это background
    task в отдельном потоке/лупе — сессию запроса переиспользовать нельзя).

    Соединение с БД НЕ держим во время долгих awaits к DeepSeek: сперва собираем
    контекст и закрываем сессию, потом генерируем, потом открываем свежую сессию
    для записи. План сохраняется атомарно в самом конце (одним replace), чтобы
    пользователь не увидел полусобранный план."""
    days = weeks * 7
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            return
        context = _build_user_context(user, db)
        chat_history = (
            db.query(ChatMessage).filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc()).limit(30).all()[::-1]
        )
        chat_context = _plan_chat_prefs(chat_history)
        stub_week = _stub_plan(user, db, 7)
        try:
            now_local = datetime.now(ZoneInfo(user.timezone)) if user.timezone else datetime.now()
        except Exception:
            now_local = datetime.now()
        start = now_local.replace(tzinfo=None)
        if not include_today:
            start += timedelta(days=1)
    finally:
        db.close()   # отпускаем соединение на время генерации

    try:
        workouts_data = await generate_plan_chunked(context, chat_context, stub_week, days, start)
        db = SessionLocal()
        try:
            replace_upcoming_workouts(user_id, db, workouts_data, start, horizon_days=days)
            job = db.get(PlanJob, job_id)
            if job:
                job.status = "done"
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.exception("run_plan_job failed (user %s, weeks %s): %s", user_id, weeks, e)
        db = SessionLocal()
        try:
            job = db.get(PlanJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(e)[:500]
                db.commit()
        finally:
            db.close()


async def generate_training_plan(
    user: User, db: Session, chat_history: list[ChatMessage] | None = None,
    days: int = 7, include_today: bool = False,
) -> list[dict]:
    """
    Просит AI сгенерировать план тренировок на `days` дней (7 — неделя, 28 —
    месяц, 84 — 3 месяца). Для длинных горизонтов промпт требует периодизацию.
    Возвращает список словарей [{workout_type, description, distance_km, target_pace_min_km}]
    ПО ПОРЯДКУ дней (элемент i = i-й день от старта плана — см. include_today).
    """
    if _STUB_MODE:
        return _stub_plan(user, db, days)

    context = _build_user_context(user, db)
    chat_context = _plan_chat_prefs(chat_history)

    today_str = datetime.now().strftime('%d.%m.%Y')
    start_date = datetime.now() if include_today else datetime.now() + timedelta(days=1)
    _WD = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
    start_str = f"{start_date.strftime('%d.%m.%Y')} ({_WD[start_date.weekday()]})"
    weeks = max(1, round(days / 7))
    if days <= 7:
        horizon_line = f"на ближайшие 7 дней (начиная с {start_str})"
        periodization = "Расставь отдых и длинную пробежку разумно в течение недели."
        desc_rule = "описание тренировки на русском, 1-2 предложения"
    else:
        horizon_line = f"на ближайшие {days} дней (~{weeks} недель), начиная с {start_str}"
        periodization = (
            "Это ДЛИННЫЙ план — обязательно сделай периодизацию: чередуй развивающие "
            "недели с разгрузочными (каждая 3-4-я неделя легче на ~20-30%), наращивай "
            "недельный объём не быстрее ~10% и откатывай его в разгрузочные недели, "
            "1 длинная пробежка в неделю с плавным ростом, соблюдай правило 80/20. "
            "Если у спортсмена задана дата целевого старта — подведи объём к пику за "
            "2-3 недели до неё и сделай подводку (taper) перед стартом."
        )
        desc_rule = "описание КОРОТКО, 3-8 слов (план длинный — без воды)"

    prompt = f"""{context}{chat_context}

Сегодня: {today_str}. Составь персональный план тренировок {horizon_line} для этого спортсмена.
Верни ТОЛЬКО валидный JSON-объект строго вида {{"plan": [ ... {days} объектов ... ]}} — \
ровно {days} объектов ПО ПОРЯДКУ: элемент 0 = {start_str}, 1 = день после, ..., {days - 1} = через {days - 1} дней от старта плана. \
Не раскладывай дни отдельными ключами объекта — только массив в "plan".

{_plan_item_schema(desc_rule)}

Учитывай цели спортсмена, его текущий уровень и принцип 80/20. {periodization}
Только JSON, без пояснений."""

    # См. комментарий в chat_response — освобождаем соединение на время ожидания
    # DeepSeek. Вызывающий код (generate_plan_ai/build_and_save_plan) нарочно не
    # оставляет здесь ничего незакоммиченного до этого await.
    db.close()

    try:
        resp = await _chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            # ~70-75 токенов на день; потолок 8000 (лимит вывода модели).
            max_tokens=min(8000, max(1200, days * 75)),
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        parsed = json.loads(raw)
        plan = _extract_plan_list(parsed)
        # Пустой план недопустим: раньше он молча уходил дальше и приводил к
        # удалению текущего плана без замены. Если распарсить дни не удалось —
        # это негодный ответ модели, отдаём непустой stub, а не пустоту.
        if not plan:
            logger.error("DeepSeek plan: не удалось извлечь дни из ответа, откат на stub. raw=%.400s", raw)
            return _stub_plan(user, db, days)
        return plan[:days]
    except Exception as e:
        logger.error("DeepSeek plan error: %s", e)
        return _stub_plan(user, db, days)


async def generate_insights(user: User, db: Session) -> list[str]:
    """Генерирует 2-4 коротких инсайта для дашборда."""
    if _STUB_MODE:
        return _stub_insights(user, db)

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
        resp = await _chat(
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


def _stub_plan(user: User, db: Session, days: int = 7) -> list[dict]:
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
    week = plans.get(goal_type, plans["default"])
    # Размножаем недельный шаблон на весь горизонт (стаб без периодизации —
    # это заглушка на случай отсутствия/сбоя ключа DeepSeek).
    return [dict(week[i % 7]) for i in range(days)]


def _stub_insights(user: User, db: Session) -> list[str]:
    tz = None
    if user.timezone:
        try:
            tz = ZoneInfo(user.timezone)
        except Exception:
            tz = None
    since = datetime.now(tz) - timedelta(days=30)
    # Только бег — иначе ходьба/велотренировки/силовая считаются "пробежками",
    # а их темп/дистанция смешиваются с беговыми в тех же инсайтах.
    activities = db.query(Activity).filter(
        Activity.user_id == user.id, Activity.activity_type == "run", Activity.date >= since
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
