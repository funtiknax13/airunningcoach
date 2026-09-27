"""Алгоритмический планировщик тренировок (без ИИ).

Строит план в том же формате отрезков, что и ИИ (см. plan_format): структура и
имена зон, числа считает код по зонам пользователя. Служит и полноценным
генератором, и «конвертом» ограничений: те же лимиты (объём недели, длинная,
число дней) проверяют и план, который вернул ИИ (enforce_envelope).

ВАЖНО: пороги и коэффициенты ниже — ориентиры для проектирования (консервативные
по духу «не быстрее ~10% в неделю, каждая 4-я неделя легче»), а не выверенная
методика. Их нужно показать тренеру/ревьюеру до серьёзного использования.
Числовые значения по уровню (LEVEL_*) — допущения на случай, когда данных нет.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.services import plan_format as pf
from app.services.zones import Zones, recent_runs

LEVEL_DEFAULT_KM = {"beginner": 8.0, "intermediate": 15.0, "advanced": 25.0}   # допущение: км/нед без данных
LEVEL_LONG_CAP = {"beginner": 5.0, "intermediate": 10.0, "advanced": 16.0}      # допущение: потолок длинной без данных
GROWTH = 1.08                 # рост недельного объёма (≤ ~10%)
DELOAD_FACTOR = 0.75          # каждая 4-я календарная неделя плана легче
WEEK_CAP_TOLERANCE = 1.10     # допуск сверх целевого объёма при проверке плана ИИ
LONG_GROWTH = 1.08
LONG_OVER_LONGEST = 1.15      # длинная не длиннее ~115% самой длинной недавней
SESSION_MIN_KM = 2.0
LONG_FLOOR_SHARE = 0.7        # длинная не короче ~70% самой длинной недавней (не откатываем назад)
BEGINNER_MAX_DAYS = 4
BEGINNER_BASELINE_KM = 6.0    # ниже — старт «бег/ходьба по времени»

# Раскладка для длинной в воскресенье (0=Пн..6=Вс); для другого дня сдвигается.
WEEKDAY_TABLE = {
    1: [6], 2: [3, 6], 3: [1, 3, 6], 4: [0, 2, 4, 6],
    5: [0, 1, 3, 5, 6], 6: [0, 1, 3, 4, 5, 6],
}
W_LONG, W_QUALITY, W_EASY = 1.5, 1.1, 0.8

# Бег/ходьба для новичков: (повторы, бег с, ходьба с). Иллюстративная схема для ревью.
BEGINNER_RUN_WALK = [
    (8, 60, 90), (6, 90, 90), (5, 180, 90), (4, 300, 120), (3, 480, 120), (2, 720, 120),
]
BEGINNER_CONTINUOUS_MIN = [20, 25, 30]     # затем +5 мин за неделю до потолка
BEGINNER_CONTINUOUS_MAX = 45

COMMENTS = {
    "easy": "Спокойный бег в разговорном темпе: можете свободно говорить.",
    "long": "Длинная пробежка: бегите ровно и спокойно, скорость не важна.",
    "tempo": "Комфортно-тяжёлый темп: можете сказать лишь несколько слов подряд.",
    "interval": "Быстрые повторы с лёгкой трусцой между ними; не гонитесь за скоростью в первых повторах.",
}


@dataclass
class PlanRequest:
    start: datetime                       # первый день плана (учитывается только дата)
    days: int
    zones: Zones
    training_days: Optional[int] = None
    long_run_day: Optional[int] = None    # 0=Пн..6=Вс
    level: Optional[str] = None
    goal: Optional[str] = None            # 5k|10k|half_marathon|marathon|fitness
    weekly_km_profile: Optional[float] = None
    history_avg_km: Optional[float] = None     # средний недельный объём за 4 недели
    history_runs_4w: int = 0
    longest_run_km: Optional[float] = None
    goal_date: Optional[date] = None
    completed_beginner_sessions: int = 0
    recent_rpe: list[str] = field(default_factory=list)   # от старых к новым


# ── исходные данные из истории ──────────────────────────────────────────────

def history_stats(activities, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    runs4 = recent_runs(activities, now, weeks=4)
    runs8 = recent_runs(activities, now, weeks=8)
    avg_km = None
    if runs4:
        # Делим на число реально «прожитых» недель (от первой пробежки в окне, 1..4), а не
        # всегда на 4: у того, кто начал бегать 2 недели назад, иначе объём занижается вдвое.
        first = min(_utc(a.date) for a in runs4)
        span_weeks = min(4, max(1, -(-(now - first).days // 7)))
        avg_km = sum(a.distance_km for a in runs4) / span_weeks
    return {
        "avg_km": avg_km,
        "runs_4w": len(runs4),
        "longest_km": max((a.distance_km for a in runs8), default=None),
    }


def long_floor_km(req: "PlanRequest", w: int, target_km: float | None = None) -> float:
    """Нижняя граница длинной для недели w: ~70% самой длинной недавней пробежки (не откатываем
    человека назад), не выше потолка и ~60% недельного объёма. В разгрузочную неделю — 0."""
    if not req.longest_run_km or (w + 1) % 4 == 0:
        return 0.0
    floor = min(long_cap_km(req, w), LONG_FLOOR_SHARE * req.longest_run_km)
    if target_km is not None:
        floor = min(floor, 0.6 * target_km)
    return floor


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def baseline_km(req: PlanRequest) -> float:
    if req.history_runs_4w >= 3 and req.history_avg_km:
        return req.history_avg_km
    if req.weekly_km_profile is not None:
        return req.weekly_km_profile        # 0 = «сейчас не бегаю» → режим новичка
    return LEVEL_DEFAULT_KM.get(req.level or "", LEVEL_DEFAULT_KM["intermediate"])


def is_beginner_mode(req: PlanRequest) -> bool:
    base = baseline_km(req)
    no_history = req.history_runs_4w < 3
    return bool(no_history and base < BEGINNER_BASELINE_KM
                and (req.level == "beginner" or (req.weekly_km_profile or 0) == 0))


def long_cap_km(req: PlanRequest, week_idx: int = 0) -> float:
    if req.longest_run_km:
        cap = max(3.0, req.longest_run_km * LONG_OVER_LONGEST)
    else:
        cap = LEVEL_LONG_CAP.get(req.level or "", LEVEL_LONG_CAP["intermediate"])
    return cap * (LONG_GROWTH ** week_idx)


# ── календарные недели плана ────────────────────────────────────────────────

def _start_date(req: PlanRequest) -> date:
    return req.start.date() if isinstance(req.start, datetime) else req.start


def calendar_weeks(req: PlanRequest) -> list[dict]:
    """[{monday, indices:[i...]}] в порядке плана."""
    d0 = _start_date(req)
    weeks: dict[date, list[int]] = {}
    for i in range(req.days):
        d = d0 + timedelta(days=i)
        weeks.setdefault(d - timedelta(days=d.weekday()), []).append(i)
    return [{"monday": m, "indices": idx} for m, idx in weeks.items()]


def week_target_km(req: PlanRequest, w: int, monday: date) -> float:
    base = baseline_km(req)
    target = base * (GROWTH ** w)
    # разгрузка каждой 4-й недели: 3 недели рост, потом откат
    if (w + 1) % 4 == 0:
        target = base * (GROWTH ** (w - 1)) * DELOAD_FACTOR
    if req.goal_date:
        delta = (req.goal_date - monday).days
        if 0 <= delta <= 6:
            target *= 0.5           # неделя старта
        elif 7 <= delta <= 13:
            target *= 0.75          # подводка
    if w == 0 and len(req.recent_rpe) >= 2 and req.recent_rpe[-2:] == ["hard", "hard"]:
        target *= 0.9
    return target


# ── раскладка недели ────────────────────────────────────────────────────────

def choose_weekdays(n: int, long_day: int) -> list[int]:
    n = max(1, min(6, n))
    shift = (long_day - 6) % 7
    return sorted((d + shift) % 7 for d in WEEKDAY_TABLE[n])


def _circ(a: int, b: int) -> int:
    d = abs(a - b) % 7
    return min(d, 7 - d)


def quality_count(req: PlanRequest, n: int, w: int, deload: bool, beginner: bool) -> int:
    if beginner or deload or n < 3:
        return 0
    if req.zones.pace_confidence == "none":
        return 0
    if req.zones.pace_confidence == "low" and w < 2:
        return 0
    if w == 0 and len(req.recent_rpe) >= 2 and req.recent_rpe[-2:] == ["hard", "hard"]:
        return 0
    if req.goal == "fitness":
        return 0
    if req.level == "beginner":
        return 1 if (n >= 5 and w >= 2) else 0
    if req.level == "advanced":
        return 2 if n >= 5 else 1
    return 1


def pick_quality_days(weekdays: list[int], long_day: int, q: int) -> list[int]:
    chosen: list[int] = []
    pool = [d for d in weekdays if d != long_day and _circ(d, long_day) >= 2]
    while len(chosen) < q and pool:
        anchors = chosen + [long_day]
        best = max(pool, key=lambda d: (min(_circ(d, a) for a in anchors), -d))
        chosen.append(best)
        pool.remove(best)
    return sorted(chosen)


def _r5(x: float) -> float:
    return round(x * 2) / 2


def _easy(km: float, wtype: str = "easy") -> dict:
    return {"workout_type": wtype, "comment": COMMENTS.get(wtype),
            "segments": [{"kind": "run", "zone": "easy" if wtype == "easy" else "long", "distance_km": km}]}


def _tempo(km: float) -> Optional[dict]:
    warm = cool = 1.0 if km >= 4.5 else 0.5
    main = _r5(km - warm - cool)
    if main < 1.5:
        return None
    return {"workout_type": "tempo", "comment": COMMENTS["tempo"], "segments": [
        {"kind": "warmup", "zone": "easy", "distance_km": warm},
        {"kind": "steady", "zone": "tempo", "distance_km": main},
        {"kind": "cooldown", "zone": "easy", "distance_km": cool},
    ]}


def _interval(km: float) -> Optional[dict]:
    warm, cool = (1.5 if km >= 6 else 1.0), 1.0
    body = km - warm - cool
    # при малом объёме — короткие повторы 400 м (с трусцой 200 м), иначе классические 800/400
    if body >= 3.6:
        rep_m, rec_m = 800, 400
    elif body >= 1.8:
        rep_m, rec_m = 400, 200
    else:
        return None
    reps = int(round(body / ((rep_m + rec_m) / 1000)))
    if reps < 3:
        return None
    reps = min(reps, 10)
    return {"workout_type": "interval", "comment": COMMENTS["interval"], "segments": [
        {"kind": "warmup", "zone": "easy", "distance_km": warm},
        {"kind": "intervals", "zone": "interval", "reps": reps, "distance_m": rep_m,
         "recovery": {"distance_m": rec_m, "zone": "recovery"}},
        {"kind": "cooldown", "zone": "easy", "distance_km": cool},
    ]}


def quality_types(req: "PlanRequest", w: int, q: int) -> list[str]:
    """Какие качественные тренировки ставить на неделю w (индекс календарной недели плана)."""
    if q >= 2:
        return ["tempo", "interval"]
    if q == 1:
        return ["interval"] if (req.goal in ("5k", "10k") and w % 2 == 1) else ["tempo"]
    return []


def _rest() -> dict:
    return {"workout_type": "rest", "segments": [], "comment": None}


def beginner_session(bw: int) -> dict:
    """Сессия начинающего для недели программы bw (0-based): ходьба, бег/ходьба, ходьба."""
    warm = {"kind": "walk", "duration_min": 5}
    cool = {"kind": "walk", "duration_min": 5}
    if bw < len(BEGINNER_RUN_WALK):
        reps, run_s, walk_s = BEGINNER_RUN_WALK[bw]
        main = {"kind": "run_walk", "zone": "easy", "reps": reps, "run_s": run_s, "walk_s": walk_s}
    else:
        idx = bw - len(BEGINNER_RUN_WALK)
        minutes = (BEGINNER_CONTINUOUS_MIN[idx] if idx < len(BEGINNER_CONTINUOUS_MIN)
                   else min(BEGINNER_CONTINUOUS_MAX, BEGINNER_CONTINUOUS_MIN[-1] + 5 * (idx - len(BEGINNER_CONTINUOUS_MIN) + 1)))
        main = {"kind": "run", "zone": "easy", "duration_min": minutes}
    return {"workout_type": "easy", "comment": COMMENTS["easy"], "segments": [warm, main, cool]}


# ── основной генератор ──────────────────────────────────────────────────────

def _session_km(W: float, roles: dict[int, str], long_cap: float,
                long_floor: float = 0.0) -> dict[int, float]:
    weights = {d: {"long": W_LONG, "quality": W_QUALITY}.get(r, W_EASY) for d, r in roles.items()}
    total = sum(weights.values()) or 1.0
    out = {}
    long_days = [d for d, r in roles.items() if r == "long"]
    long_km = 0.0
    for d in long_days:
        share = W * weights[d] / total
        # пол длинной не больше ~60% недельного объёма: у бегуна с малым средним, но одной
        # длинной пробежкой в истории не раздуваем всю неделю ради неё
        floor = min(long_floor, long_cap, 0.6 * W)
        long_km = min(long_cap, max(share, floor))
        out[d] = max(SESSION_MIN_KM, _r5(long_km))
    # остальное распределяем между остальными сессиями по весам (объём недели сохраняется)
    others = {d: w for d, w in weights.items() if d not in long_days}
    rest_total = sum(others.values()) or 1.0
    remaining = max(0.0, W - long_km)
    for d, w in others.items():
        out[d] = max(SESSION_MIN_KM, _r5(remaining * w / rest_total)) if long_days else \
            max(SESSION_MIN_KM, _r5(W * w / total))
    return out


def generate_plan(req: PlanRequest) -> tuple[list[dict], dict]:
    """(канонические дни плана по порядку, метаданные)."""
    n_req = req.training_days or (4 if req.level != "beginner" else 3)
    beginner = is_beginner_mode(req)
    n = min(n_req, BEGINNER_MAX_DAYS) if beginner else n_req
    long_day = req.long_run_day if req.long_run_day is not None else 6
    weekdays = choose_weekdays(n, long_day)

    d0 = _start_date(req)
    days: list[Optional[dict]] = [None] * req.days
    weeks = calendar_weeks(req)
    bw0 = req.completed_beginner_sessions // max(1, len(weekdays))
    if beginner and len(req.recent_rpe) >= 1 and req.recent_rpe[-1] == "hard":
        bw0 = max(0, bw0 - 1)          # тяжело — повторяем прошлую неделю программы

    for w, wk in enumerate(weeks):
        deload = (w + 1) % 4 == 0
        target = week_target_km(req, w, wk["monday"])
        q = quality_count(req, len(weekdays), w, deload, beginner)
        q_days = pick_quality_days(weekdays, long_day, q)
        roles = {d: ("long" if d == long_day and len(weekdays) >= 2 else
                     "quality" if d in q_days else "easy") for d in weekdays}
        if len(weekdays) == 1:
            roles = {weekdays[0]: "easy"}
        cap_w = long_cap_km(req, w)
        floor_w = long_floor_km(req, w)   # в разгрузочную неделю пол не действует
        km_by_day = _session_km(target, roles, cap_w, floor_w)
        q_types = quality_types(req, w, len(q_days))

        for i in wk["indices"]:
            wd = (d0 + timedelta(days=i)).weekday()
            if wd not in roles:
                days[i] = _rest()
                continue
            if beginner:
                days[i] = beginner_session(bw0 + w)
                continue
            role, km = roles[wd], km_by_day[wd]
            if role == "long":
                days[i] = _easy(km, "long")
            elif role == "quality":
                qt = q_types[q_days.index(wd)] if q_days.index(wd) < len(q_types) else "tempo"
                # при малом объёме интервалы не помещаются — пробуем темповую, затем лёгкий бег
                built = _interval(km) if qt == "interval" else None
                built = built or _tempo(km)
                days[i] = built or _easy(km)
            else:
                days[i] = _easy(km)

    meta = {
        "mode": "beginner" if beginner else "standard",
        "baseline_km": round(baseline_km(req), 1),
        "training_days": n,
        "training_days_requested": n_req,
        "long_run_day": long_day,
    }
    return [d if d is not None else _rest() for d in days], meta


# ── ограничения («конверт») и проверка чужих планов ────────────────────────

def compute_constraints(req: PlanRequest) -> dict:
    """Лимиты, в которые обязан укладываться любой план (и ИИ, и алгоритм)."""
    beginner = is_beginner_mode(req)
    n = req.training_days or (4 if req.level != "beginner" else 3)
    if beginner:
        n = min(n, BEGINNER_MAX_DAYS)
    weeks = []
    for w, wk in enumerate(calendar_weeks(req)):
        cap = week_target_km(req, w, wk["monday"]) * WEEK_CAP_TOLERANCE
        weeks.append({"monday": wk["monday"].isoformat(), "days": len(wk["indices"]),
                      "cap_km": round(cap, 1), "long_cap_km": round(long_cap_km(req, w), 1),
                      "deload": (w + 1) % 4 == 0})
    return {
        "beginner": beginner, "baseline_km": round(baseline_km(req), 1),
        "training_days": n, "long_run_day": req.long_run_day if req.long_run_day is not None else 6,
        "quality_allowed": req.zones.pace_confidence != "none" and not beginner,
        "weeks": weeks,
    }


_DROP_ORDER = {"recovery": 0, "easy": 1, "tempo": 2, "interval": 3, "long": 4}


def _day_km(day: dict) -> float:
    return sum(s.get("distance_km", 0) for s in day["segments"])


def training_days_limits(training_days: int | None) -> Optional[tuple[int, int]]:
    """(мин, макс) тренировочных дней в неделю. «5+» в интерфейсе хранится как 5 → 5-6."""
    if not training_days:
        return None
    return (5, 6) if training_days >= 5 else (training_days, training_days)


def cap_training_days(days: list[dict], start: datetime, training_days: int | None) -> list[dict]:
    """Не больше лимита тренировочных (не rest) дней в каждой календарной неделе Пн-Вс.
    Лишние → отдых, снимаются сначала recovery, затем короткие easy; недостающие
    дни не добавляем. Работает и с сырыми словарями модели, и с каноническими днями."""
    limits = training_days_limits(training_days)
    if not limits:
        return days
    max_days = limits[1]
    out = [dict(d) for d in days]
    weeks: dict = {}
    for i in range(len(out)):
        d = (start + timedelta(days=i)).date()
        weeks.setdefault(d - timedelta(days=d.weekday()), []).append(i)

    def km(d):
        return _day_km(d) if "segments" in d else (d.get("distance_km") or 0)

    for idxs in weeks.values():
        cap = max_days if len(idxs) == 7 else -(-max_days * len(idxs) // 7)
        active = [i for i in idxs if out[i].get("workout_type", "easy") != "rest"]
        extra = len(active) - cap
        if extra <= 0:
            continue
        active.sort(key=lambda i: (_DROP_ORDER.get(out[i].get("workout_type"), 1), km(out[i])))
        for i in active[:extra]:
            out[i] = {"workout_type": "rest", "description": "Отдых", "segments": [],
                      "comment": None, "distance_km": None, "duration_min": None,
                      "target_pace_min_km": None, "plan_structure": None,
                      "plan_source": out[i].get("plan_source")}
    return out


def enforce_envelope(days: list[dict], req: PlanRequest) -> list[dict]:
    """Приводит канонический план (например, от ИИ) к ограничениям: число дней,
    длинная не длиннее потолка, недельный объём не выше цели (пропорциональное
    уменьшение). Дни без известной дистанции (по времени) не масштабируем."""
    out = cap_training_days(days, _start_date_dt(req), req.training_days)
    zones = req.zones
    for w, wk in enumerate(calendar_weeks(req)):
        long_cap = long_cap_km(req, w)
        target_w = week_target_km(req, w, wk["monday"])
        floor = long_floor_km(req, w, target_w)
        for i in wk["indices"]:
            if out[i]["workout_type"] == "long":
                km = pf.day_distance_km(out[i], zones)
                if km and km > long_cap:
                    out[i] = pf.scale_day(out[i], long_cap / km)
                elif km and floor and km < floor * 0.95:
                    # ИИ занизил длинную относительно уже пробегавшегося — подтягиваем до пола
                    out[i] = pf.scale_day(out[i], floor / km)
        cap = week_target_km(req, w, wk["monday"]) * WEEK_CAP_TOLERANCE
        kms = [pf.day_distance_km(out[i], zones) for i in wk["indices"]]
        if any(k is None for k in kms):
            continue
        total = sum(kms)
        if total > cap > 0:
            factor = cap / total
            for i in wk["indices"]:
                if out[i]["segments"]:
                    out[i] = pf.scale_day(out[i], factor)
    return out


def _start_date_dt(req: PlanRequest) -> datetime:
    s = req.start
    return s if isinstance(s, datetime) else datetime.combine(s, datetime.min.time())
