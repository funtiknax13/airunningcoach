"""ИИ-генератор плана в формате отрезков (plan_format) с проверкой кодом.

ИИ выбирает СТРУКТУРУ и ЗОНЫ и пишет короткий комментарий; числа (темп, пульс,
средний темп) не пишет — их подставляет код по зонам пользователя. Ответ
проверяется: невалидный формат → один повтор с описанием ошибки → откат на
алгоритмический планировщик (planner) с честной пометкой; ограничения (число дней,
потолок длинной, недельный объём, качественные тренировки при неизвестных зонах)
гарантирует код (planner.enforce_envelope), а не промпт.

Соглашение plan_source: 'ai' — составил ИИ; 'rules' — алгоритм ВМЕСТО ИИ (сбой или
ИИ недоступен, показываем пометку); 'algo' — алгоритм по замыслу (программа для
начинающих), без пометки о сбое.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Awaitable, Callable, Optional

from app.services import plan_format as pf
from app.services import planner as pl

logger = logging.getLogger(__name__)

CHUNK_DAYS = 14
_WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
_WD_LONG = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


@dataclass
class PlanOutcome:
    workouts: list[dict]
    source: str                       # ai | rules | algo
    reason: Optional[str] = None      # no_ai | ai_failed | invalid | beginner
    meta: dict = field(default_factory=dict)


class AiPlanError(Exception):
    """ИИ не дал пригодный план (сбой провайдеров или невалидный формат)."""


# ── разбор ответа ───────────────────────────────────────────────────────────

def _extract_list(parsed: Any) -> list:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


def parse_days(text: str, n: int) -> list[dict]:
    """Текст ответа модели -> ровно n канонических дней или исключение."""
    parsed = json.loads(text.strip())
    raw = _extract_list(parsed)
    if len(raw) < n:
        raise pf.PlanFormatError(f"вернулось {len(raw)} дней вместо {n}")
    return [pf.normalize_day(d) for d in raw[:n]]


# ── промпт ──────────────────────────────────────────────────────────────────

_SCHEMA = """Формат объекта дня:
{"workout_type": "easy|tempo|interval|long|recovery|rest",
 "segments": [ ... ],      // для rest — []
 "comment": "1-2 коротких предложения совета к этой тренировке"}

Виды отрезков (segments):
{"kind":"run","zone":"easy|long|recovery","distance_km":6}                    // ровный бег (или "duration_min")
{"kind":"warmup","distance_km":1} и {"kind":"cooldown","distance_km":1}      // разминка и заминка
{"kind":"steady","zone":"tempo","distance_km":4}                            // темповой блок
{"kind":"intervals","zone":"interval","reps":6,"distance_m":800,"recovery":{"distance_m":400,"zone":"recovery"}}
{"kind":"run_walk","zone":"easy","reps":8,"run_s":60,"walk_s":90}           // бег/ходьба
{"kind":"walk","duration_min":20}
Зоны: recovery, easy, long, tempo, interval."""


def _weeks_lines(req: pl.PlanRequest, lo: int, hi: int) -> str:
    lines = []
    for w, wk in enumerate(pl.calendar_weeks(req)):
        idx = [i for i in wk["indices"] if lo <= i < hi]
        if not idx:
            continue
        cap = pl.week_target_km(req, w, wk["monday"]) * pl.WEEK_CAP_TOLERANCE
        deload = (w + 1) % 4 == 0
        q = pl.quality_count(req, pl.compute_constraints(req)["training_days"], w, deload,
                             pl.is_beginner_mode(req))
        qt = pl.quality_types(req, w, q)
        hint = ""
        if qt:
            names = {"tempo": "темповая", "interval": "интервальная"}
            hint = "; качественная тренировка недели — " + " и ".join(names[t] for t in qt)
        target = pl.week_target_km(req, w, wk["monday"])
        floor = pl.long_floor_km(req, w, target)
        long_txt = (f"длинная {floor:.0f}–{pl.long_cap_km(req, w):.0f} км" if floor
                    else f"длинная не более {pl.long_cap_km(req, w):.0f} км")
        lines.append(
            f"- неделя с {wk['monday']:%d.%m}: недельный объём около {target:.0f} км (не более {cap:.0f}), "
            f"{long_txt}{hint}"
            + (" (разгрузочная неделя)" if deload else ""))
    return "\n".join(lines)


def build_prompt(req: pl.PlanRequest, context: str, chat_context: str, lo: int, hi: int,
                 prev_tail: list[dict]) -> str:
    start = pl._start_date_dt(req) + timedelta(days=lo)
    n = hi - lo
    c = pl.compute_constraints(req)
    rule_days = c["training_days"]
    long_name = _WD_LONG[c["long_run_day"]]
    quality = ("Тренировки tempo/interval допустимы, но не более одной-двух в неделю и не в разгрузочную неделю."
               if c["quality_allowed"] else
               "Темп и интервалы пока НЕ ставь (данных о темпе бегуна мало) — только easy/long и отдых.")
    tail = ""
    if prev_tail:
        tail = "\nПредыдущие дни (продолжай логично): " + "; ".join(
            f"{d['workout_type']} {pf.day_distance_km(d, req.zones) or ''}".strip() for d in prev_tail)
    return f"""{context}{chat_context}

Составь план тренировок на {n} дней, начиная с {start:%d.%m.%Y} ({_WD[start.weekday()]}).
Верни ТОЛЬКО JSON вида {{"plan": [ ... {n} объектов ПО ПОРЯДКУ ... ]}}: элемент 0 = {start:%d.%m.%Y}, следующий — день после и т.д.{tail}

ВАЖНО: ты выбираешь структуру и зоны. Темп и пульс числами НЕ пиши — систему подставит сама по данным бегуна.

{_SCHEMA}

ЖЁСТКИЕ ПРАВИЛА (нарушать нельзя, система проверит):
- В каждой календарной неделе (Пн-Вс) — ровно {rule_days} тренировочных дней, остальные "rest". В неполной неделе на краях плана пропорционально меньше.
- Длинная пробежка — раз в неделю, желательно в {long_name}.
{_weeks_lines(req, lo, hi)}
- {quality}
- Правило 80/20: большая часть бега лёгкая.
Только JSON, без пояснений."""


# ── вызов ИИ ────────────────────────────────────────────────────────────────

ChatFn = Callable[..., Awaitable[Any]]

RETRY_DELAY_S = 4


def _is_transient(e: Exception) -> bool:
    text = str(e).lower()
    if "429" in text or "quota" in text or "rate limit" in text or "rate_limit" in text:
        return False
    return any(k in text for k in ("503", "502", "504", "unavailable", "overloaded",
                                   "high demand", "timed out", "timeout", "connection"))


async def _ai_chunk(chat: ChatFn, system: str, prompt: str, n: int) -> list[dict]:
    note = ""
    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = await chat(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt + note}],
                max_tokens=min(4500, max(900, n * 110)),
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content
        except Exception as e:                          # все провайдеры недоступны
            # Временный сбой (503/перегрузка/таймаут) стоит один раз повторить: месячный план
            # «всё или ничего», и из-за одного 503 не хочется терять весь план ИИ. Квоту (429)
            # повтор не лечит.
            if attempt == 0 and _is_transient(e):
                logger.warning("AI plan: временный сбой провайдера, повтор через %ss: %s", RETRY_DELAY_S, e)
                await asyncio.sleep(RETRY_DELAY_S)
                continue
            raise AiPlanError(f"ai_failed: {e}") from e
        try:
            return parse_days(text, n)
        except (pf.PlanFormatError, ValueError) as e:  # ValueError включает JSONDecodeError
            last = e
            note = f"\n\nПредыдущий ответ отклонён: {e}. Исправь и верни корректный JSON строго по формату."
            logger.warning("AI plan chunk invalid (attempt %d): %s", attempt + 1, e)
    raise AiPlanError(f"invalid: {last}")


def sanitize_quality(days: list[dict], req: pl.PlanRequest) -> list[dict]:
    """tempo/interval там, где по правилам их быть не должно (нет зон, разгрузка,
    цель «для здоровья», ...), превращаем в лёгкий бег той же дистанции."""
    c = pl.compute_constraints(req)
    n = c["training_days"]
    out = [dict(d) for d in days]
    for w, wk in enumerate(pl.calendar_weeks(req)):
        allowed = pl.quality_count(req, n, w, (w + 1) % 4 == 0, c["beginner"])
        seen = 0
        for i in wk["indices"]:
            if out[i]["workout_type"] not in ("tempo", "interval"):
                continue
            seen += 1
            if seen > allowed:
                km = pf.day_distance_km(out[i], req.zones) or 5.0
                out[i] = {"workout_type": "easy", "comment": out[i].get("comment"),
                          "segments": [{"kind": "run", "zone": "easy", "distance_km": round(km * 2) / 2 or 2.0}]}
    return out


# ── главный вход ────────────────────────────────────────────────────────────

def _to_workouts(days: list[dict], req: pl.PlanRequest, source: str) -> list[dict]:
    return [pf.build_workout(d, req.zones, source) for d in days]


def rules_outcome(req: pl.PlanRequest, source: str, reason: str) -> PlanOutcome:
    days, meta = pl.generate_plan(req)
    return PlanOutcome(_to_workouts(days, req, source), source, reason, meta)


async def generate(req: pl.PlanRequest, *, context: str, chat_context: str,
                   chat: Optional[ChatFn], system: str, ai_enabled: bool = True) -> PlanOutcome:
    """План на req.days дней. Никогда не бросает исключение из-за ИИ: при любом сбое —
    алгоритмический план с пометкой. chat=None или ai_enabled=False — ИИ не используется."""
    constraints = pl.compute_constraints(req)
    if constraints["beginner"]:
        return rules_outcome(req, "algo", "beginner")
    if not ai_enabled or chat is None:
        return rules_outcome(req, "rules", "no_ai")

    try:
        days: list[dict] = []
        lo = 0
        while lo < req.days:
            hi = min(req.days, lo + (req.days if req.days <= 7 else CHUNK_DAYS))
            prompt = build_prompt(req, context, chat_context, lo, hi, days[-3:])
            days.extend(await _ai_chunk(chat, system, prompt, hi - lo))
            lo = hi
        days = sanitize_quality(days, req)
        days = pl.enforce_envelope(days, req)
        return PlanOutcome(_to_workouts(days, req, "ai"), "ai", None, {"constraints": constraints})
    except AiPlanError as e:
        reason = "invalid" if str(e).startswith("invalid") else "ai_failed"
        logger.error("AI plan failed (%s), fallback to rules: %s", reason, e)
        return rules_outcome(req, "rules", reason)
