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
from app.services.rate_limit import _is_premium_active
from app.services import chat_prefs, plan_ai, plan_service
from app.services.planner import cap_training_days as _cap_training_days
from app.services.zones import fmt_pace as _zone_pace

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
- Если данных о темпе/пульсе бегуна нет — НЕ выдумывай числа: скажи, чего не хватает, \n  и задай 1-2 коротких вопроса (например, какой у него комфортный темп на км). Темпы и \n  пульс называй только те, что указаны в блоке «ЗОНЫ» контекста.
- Про пересборку плана — в переписке будет блок «ПЛАН ТОЛЬКО ЧТО ПЕРЕСОБРАН» / «ПЛАН НЕ \
  ПЕРЕСОБИРАЛСЯ», перед последним сообщением пользователя — следуй ему буквально. Никогда не \
  утверждай, что обновила план, если это не подтверждено этим блоком — ты не можешь изменить \
  план просто фактом ответа.
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
    if settings.CUSTOM_AI_API_KEY and settings.CUSTOM_AI_BASE_URL and settings.CUSTOM_AI_MODEL:
        out.append({"name": "custom", "base_url": settings.CUSTOM_AI_BASE_URL,
                    "api_key": settings.CUSTOM_AI_API_KEY, "model": settings.CUSTOM_AI_MODEL})
    if settings.GROQ_API_KEY:
        out.append({"name": "groq", "base_url": settings.GROQ_BASE_URL,
                    "api_key": settings.GROQ_API_KEY, "model": settings.GROQ_MODEL,
                    "proxy": settings.GROQ_PROXY or None})
    dk = settings.DEEPSEEK_API_KEY
    if dk and dk != "your-deepseek-api-key-here":
        out.append({"name": "deepseek", "base_url": settings.DEEPSEEK_BASE_URL,
                    "api_key": dk, "model": settings.DEEPSEEK_MODEL})
    if settings.GEMINI_API_KEY:
        out.append({"name": "gemini", "base_url": settings.GEMINI_BASE_URL,
                    "api_key": settings.GEMINI_API_KEY, "model": settings.GEMINI_MODEL})
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

# Урезанный контекст для Groq (8000 токенов/мин на бесплатном тарифе — полный
# контекст активного пользователя туда не влезает одним запросом). См. chat_response().
_GROQ_ACTIVITY_LIMIT = 15
_GROQ_HISTORY_LIMIT  = 10


def _in_cooldown(name: str) -> bool:
    return time.time() < _cooldown_until.get(name, 0.0)


def _is_rate_limit(e: Exception) -> bool:
    """openai-python оборачивает 429 в RateLimitError с status_code=429 напрямую
    (не под .response) — оба реальных пути уже надёжно покрыты этими двумя
    проверками. Раньше был ещё фолбэк по подстроке `" 429" in f" {e}"` — убрал:
    он ничего не покрывал сверх этих двух (для этого SDK), зато мог случайно
    сработать на любой другой ошибке, где "429" просто встретилось в тексте."""
    return getattr(e, "status_code", None) == 429 or "RateLimit" in type(e).__name__


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


def _ordered_providers(prefer: str | None = None) -> list[dict]:
    """Провайдеры по приоритету; в кулдауне — в самый конец (пробуем как крайний
    вариант, а не пропускаем совсем, чтобы не остаться без ответа).

    prefer: имя провайдера, который должен идти первым для ЭТОГО конкретного
    запроса (см. chat_response — Premium получает полный контекст напрямую в
    DeepSeek, Basic идёт в Groq и на DeepSeek падает только при сбое). Кулдаун
    всё равно приоритетнее prefer — упавший недавно провайдер не станет первым
    только потому, что его предпочли."""
    ps = _providers()
    if prefer:
        ps = sorted(ps, key=lambda p: 0 if p["name"] == prefer else 1)
    return [p for p in ps if not _in_cooldown(p["name"])] + [p for p in ps if _in_cooldown(p["name"])]


_GEMINI_THINKING_HEADROOM = 1500


def _chat_kwargs(p, messages, max_tokens, temperature, response_format):
    kwargs = dict(model=p["model"], messages=messages, max_tokens=max_tokens, temperature=temperature)
    if p["name"] == "gemini":
        # «Думающая» модель: токены рассуждения входят в max_tokens, без запаса ответ
        # обрывается на полуслове (наблюдалось: обрезанный JSON плана).
        kwargs["max_tokens"] = max_tokens + _GEMINI_THINKING_HEADROOM
        if settings.GEMINI_REASONING_EFFORT:
            # не входит в типизированную сигнатуру openai-SDK — передаём через extra_body
            kwargs["extra_body"] = {"reasoning_effort": settings.GEMINI_REASONING_EFFORT}
    if response_format is not None:
        kwargs["response_format"] = response_format
        if p["name"] == "groq":
            # Groq-хостинг GPT-OSS в JSON-режиме иногда подмешивает reasoning-текст
            # прямо в content — json.loads() на нашей стороне падает, а сам Groq
            # отдаёт 400 json_validate_failed ещё до того, как ответ до нас доходит.
            # include_reasoning не входит в типизированную сигнатуру openai-SDK,
            # поэтому — через extra_body (см. docs Groq по GPT-OSS reasoning).
            kwargs["extra_body"] = {"include_reasoning": False}
    return kwargs


async def _chat(messages: list[dict], max_tokens: int, temperature: float,
                response_format: dict | None = None, compact_messages: list[dict] | None = None,
                prefer: str | None = None):
    """Асинхронный чат-запрос с failover. Порядок провайдеров — см. _ordered_providers
    (prefer). При сбое провайдера — к следующему; упавший уходит в кулдаун. Все
    упали → пробрасываем (вызывающий код уходит в свой stub).

    compact_messages: усечённый вариант messages (меньше история чата/тренировок) —
    для Groq, у которого на бесплатном тарифе жёсткий потолок 8000 токенов/мин, и
    полный контекст активного пользователя туда просто не влезает одним запросом
    (уходит 413 Payload Too Large ещё до попытки обработки). DeepSeek получает
    полный messages как обычно — сокращаем контекст только там, где это реально
    вынужденно, а не для всех подряд."""
    last_exc: Exception | None = None
    for p in _ordered_providers(prefer):
        use_messages = compact_messages if (p["name"] == "groq" and compact_messages is not None) else messages
        try:
            return await _acreate(_client_for(p), **_chat_kwargs(p, use_messages, max_tokens, temperature, response_format))
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


def _zones_context(zones) -> list[str]:
    """Блок «ЗОНЫ» для контекста тренера: числа темпа/пульса только из расчёта кода."""
    conf_ru = {"high": "высокая", "medium": "средняя", "low": "низкая", "none": "нет данных"}
    if zones.pace_confidence == "none" and zones.hr_confidence == "none":
        return ["\n=== ЗОНЫ ===", "Темп и пульс бегуна неизвестны — не называй конкретных значений."]
    names = [("recovery", "восстановление"), ("easy", "лёгкий"), ("long", "длинная"),
             ("tempo", "темповый"), ("interval", "интервалы")]
    out = [f"\n=== ЗОНЫ (оценка; точность темпа: {conf_ru[zones.pace_confidence]}, "
           f"пульса: {conf_ru[zones.hr_confidence]}) ==="]
    for key, label in names:
        parts = []
        rng = zones.pace.get(key)
        if rng:
            parts.append(f"{_zone_pace(rng[0])}–{_zone_pace(rng[1])}/км")
        hr = zones.hr.get(key)
        if hr:
            parts.append(f"пульс {hr[0]}–{hr[1]}")
        if parts:
            out.append(f"• {label}: " + ", ".join(parts))
    return out


def _build_user_context(user: User, db: Session, activity_limit: int = 60) -> str:
    """Собирает контекст пользователя в текстовый блок для системного промпта.

    activity_limit: сколько последних тренировок включать в историю — по умолчанию
    60, но для Groq (жёсткий потолок 8000 токенов/мин на бесплатном тарифе) вызывающий
    код запрашивает урезанную версию, см. _chat()/chat_response()."""
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
    pref = chat_prefs.get_pref(db, user.id)
    eff_days = chat_prefs.effective_training_days(user, pref)
    if eff_days:
        note = ""
        if pref is not None and pref.training_days and pref.training_days != user.training_days:
            note = f" (по пожеланию из чата; в профиле: {user.training_days or 'не указано'})"
        lines.append(f"Дней для тренировок: {eff_days} в неделю{note}")
    if pref is not None and pref.long_run_day is not None:
        lines.append("Длинная пробежка по пожеланию: " + ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][pref.long_run_day])
    zones, _acts = plan_service.zones_for_user(user, db)
    lines.extend(_zones_context(zones))

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
        .limit(activity_limit)
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


def _build_history(messages: list[ChatMessage], limit: int = 20) -> list[dict]:
    """Конвертирует историю чата в формат OpenAI messages.

    Только сообщения ПОЛЬЗОВАТЕЛЯ помечаются датой, когда они были написаны — без
    этого модель не может отличить «это было актуально тогда» от «это происходит
    сейчас» и путает старые даты/цели из истории с текущим положением дел.
    Ответы самого агента датой НЕ помечаются: иначе модель видит в истории свои
    же прошлые ответы с префиксом и начинает имитировать его в новых ответах —
    а на следующем вызове сюда добавляется ещё один префикс поверх уже
    сгенерированного моделью, и дата дублируется с каждым ходом (было замечено
    в проде: "[05.07.2026] [05.07.2026] [05.07.2026] ...").

    limit: по умолчанию 20 (~10 ходов), но для Groq (8000 токенов/мин на бесплатном
    тарифе) вызывающий код запрашивает урезанную версию — см. chat_response()."""
    result = []
    for m in messages[-limit:]:
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

_UNAVAILABLE_MSG = "Извините, AI-тренер временно недоступен. Попробуйте позже."


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
        return _UNAVAILABLE_MSG

    lang_instruction = "Respond in English." if lang == "en" else "Отвечай на русском языке."
    plan_status = (
        "=== ПЛАН ТОЛЬКО ЧТО ПЕРЕСОБРАН ===\nПлан уже пересчитан и сохранён прямо перед этим ответом — "
        "можешь уверенно сказать, что он обновлён и появится во вкладке «Тренировки»."
        if plan_just_regenerated else
        "=== ПЛАН НЕ ПЕРЕСОБИРАЛСЯ В ЭТОМ СООБЩЕНИИ ===\nЕсли похоже, что пользователь просит "
        "изменить план — НЕ утверждай, что уже изменила его: это не так. Прямо скажи, что для "
        "пересборки нужна явная фраза («обнови план», «пересобери план», «составь план» и т.п.) "
        "или кнопка «Создать план» на вкладке «Тренировки»."
    )
    # plan_status идёт ПЕРЕД user_message в исходящем payload (а не хранимой истории —
    # только для этого запроса к модели, как и датовые метки в _build_history ниже),
    # а НЕ внутри system: он меняется от сообщения к сообщению, а SYSTEM_PROMPT+context —
    # нет (в пределах календарного дня и без новых тренировок/целей). Если приклеить его
    # в конец system, каждое сообщение рвёт DeepSeek-кэш на самом дорогом, самом большом
    # куске промпта — на дешёвом хвосте после user-сообщения кэш и так не работает.
    outgoing_user_message = f"{plan_status}\n\n{user_message}"

    context = _build_user_context(user, db)
    system  = f"{SYSTEM_PROMPT}\n{lang_instruction}\n\n{context}"
    messages = [{"role": "system", "content": system}]
    messages += _build_history(history)
    messages.append({"role": "user", "content": outgoing_user_message})

    # Компактный вариант — специально для Groq (см. _chat()): полный context/history
    # выше у активного пользователя легко уходит за 8000 токенов/мин (потолок Groq
    # на бесплатном тарифе), запрос отклоняется целиком (413) ещё до обработки.
    # DeepSeek получает messages целиком как обычно, если Groq не справился.
    compact_context = _build_user_context(user, db, activity_limit=_GROQ_ACTIVITY_LIMIT)
    compact_system  = f"{SYSTEM_PROMPT}\n{lang_instruction}\n\n{compact_context}"
    compact_messages = [{"role": "system", "content": compact_system}]
    compact_messages += _build_history(history, limit=_GROQ_HISTORY_LIMIT)
    compact_messages.append({"role": "user", "content": outgoing_user_message})

    # Premium — сразу в DeepSeek с полным контекстом (см. messages выше), Basic —
    # в Groq с урезанным (compact_messages); сбой первого провайдера всё равно
    # уходит на второй (см. _ordered_providers/prefer) — это не "либо-либо", а
    # приоритет с graceful fallback в обе стороны. db не передаём — не нужен
    # ленивый сброс истёкшего флага здесь (db.close() ниже всё равно откатит
    # незакоммиченный flush), нужен только сам факт для выбора провайдера.
    premium = _is_premium_active(user)
    prefer = "deepseek" if premium else "groq"

    # Отдаём соединение обратно в пул на время ожидания DeepSeek (до 45с) —
    # без этого оно простаивало бы занятым весь запрос, и под несколько
    # одновременных AI-запросов пул мог исчерпаться, тормозя обычные быстрые
    # эндпоинты. Всё нужное из db уже прочитано выше в context/history — после
    # close() сессия остаётся рабочей, просто возьмёт новое соединение при
    # следующем обращении (вызывающий код чата коммитит перед этим await, так
    # что откатывать здесь нечего).
    db.close()

    try:
        resp = await _chat(messages=messages, max_tokens=800, temperature=0.7,
                            compact_messages=compact_messages, prefer=prefer)
        return _strip_date_prefix(resp.choices[0].message.content.strip())
    except Exception as e:
        logger.error("DeepSeek chat error: %s", e)
        return "Извините, AI-тренер временно недоступен. Попробуйте позже."


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










def _plan_structure_for_db(ps):
    """v2 (отрезки) сохраняем как есть — она уже нормализована в plan_format;
    легаси-структуру интервалов по-прежнему проверяем _validate_plan_structure."""
    if isinstance(ps, dict) and ps.get("version") == 2:
        return ps
    return _validate_plan_structure(ps)


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

    # Лимит частоты из профиля гарантируем здесь — это единственная точка записи
    # плана в БД (недельный, месячный по кускам и план из чата).
    owner = db.get(User, user_id)
    eff_days = chat_prefs.effective_training_days(owner, chat_prefs.get_pref(db, user_id)) if owner else None
    workouts_data = _cap_training_days(workouts_data[:horizon_days], start_date, eff_days)

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
            duration_min=w.get("duration_min"),
            completion_status="none",
            plan_structure=_plan_structure_for_db(w.get("plan_structure")),
            plan_source=w.get("plan_source"),
        ))






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










def _plan_start(user: User, include_today: bool = False) -> datetime:
    """Первый день плана в локальном времени бегуна (наивный datetime). По умолчанию —
    завтра: модель не знает, сколько от сегодня уже прошло."""
    try:
        now_local = datetime.now(ZoneInfo(user.timezone)) if user.timezone else datetime.now()
    except Exception:
        now_local = datetime.now()
    start = now_local.replace(tzinfo=None)
    return start if include_today else start + timedelta(days=1)


def load_chat_history(db: Session, user_id: int, limit: int = 30) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )


async def generate_plan_outcome(
    user: User, db: Session, chat_history: list[ChatMessage] | None,
    days: int, start: datetime,
) -> "plan_ai.PlanOutcome":
    """Единая точка генерации плана: зоны/ограничения из БД -> ИИ в формате отрезков
    с проверкой кодом -> при сбое алгоритмический план с пометкой (plan_source).
    Не бросает исключений из-за ИИ. Не пишет в БД (см. replace_upcoming_workouts)."""
    req = plan_service.build_request(user, db, start, days)
    context = _build_user_context(user, db)
    chat_context = _plan_chat_prefs(chat_history)
    # Освобождаем соединение с БД на время ожидания ИИ (см. chat_response); после
    # этого используем только уже собранные данные (req/context — обычные объекты).
    db.close()
    return await plan_ai.generate(
        req, context=context, chat_context=chat_context,
        chat=None if _STUB_MODE else _chat, system=SYSTEM_PROMPT,
    )


async def build_and_save_plan(user: User, db: Session) -> "plan_ai.PlanOutcome":
    """Генерирует недельный план и сохраняет в БД. Используется из чата."""
    chat_history = load_chat_history(db, user.id)
    start = _plan_start(user)
    outcome = await generate_plan_outcome(user, db, chat_history, 7, start)
    replace_upcoming_workouts(user.id, db, outcome.workouts, start)
    db.commit()
    return outcome


async def run_plan_job(user_id: int, weeks: int, job_id: int, include_today: bool = False) -> None:
    """Фоновая генерация длинного плана. Открывает свою сессию БД (это background
    task — сессию запроса переиспользовать нельзя). Соединение с БД не держим во время
    ожидания ИИ (generate_plan_outcome закрывает сессию). План сохраняется атомарно в
    конце; «всё или ничего»: при сбое ИИ весь план строит алгоритм (без смеси)."""
    days = weeks * 7
    try:
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if not user:
                return
            chat_history = load_chat_history(db, user_id)
            start = _plan_start(user, include_today)
            outcome = await generate_plan_outcome(user, db, chat_history, days, start)
        finally:
            db.close()

        db = SessionLocal()
        try:
            replace_upcoming_workouts(user_id, db, outcome.workouts, start, horizon_days=days)
            if outcome.source != "ai":
                from app.services.rate_limit import refund_last_usage
                refund_last_usage(db, user_id, "plan")
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
