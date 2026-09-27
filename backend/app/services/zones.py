"""Зоны темпа и пульса пользователя.

Главный принцип: числа темпа и пульса считает код по данным пользователя, а не
сочиняет модель. План хранит только имена зон (easy/tempo/...), а конкретные
диапазоны подставляются отсюда (см. plan_format.resolve_structure).

Все коэффициенты ниже — эвристические ориентиры (по мотивам общепринятых зон
Дэниелса/Карвонена), а не медицинские или точные значения. Их нужно показывать
пользователю как оценку и проверять тестом/ревью тренера, если планируется
опираться на них жёстко. Точность зон растёт с данными: результат > история
пробежек > самооценка > неизвестно.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Optional

ZONE_KEYS = ("recovery", "easy", "long", "tempo", "interval")

RIEGEL_EXPONENT = 1.06
EASY_TO_5K_RATIO = 1.30          # лёгкий темп ≈ темп на 5 км × 1.30

# Множители лёгкого темпа e для границ зоны: (быстрая граница, медленная граница).
PACE_RATIOS: dict[str, tuple[float, float]] = {
    "recovery": (1.08, 1.22),
    "easy":     (0.97, 1.08),
    "long":     (0.99, 1.10),
    "tempo":    (0.81, 0.86),
    "interval": (0.73, 0.78),
}

# Доли резерва пульса (Карвонен): resting + доля * (max - resting)
HR_RESERVE_PCT: dict[str, tuple[float, float]] = {
    "recovery": (0.50, 0.60),
    "easy":     (0.60, 0.70),
    "long":     (0.60, 0.72),
    "tempo":    (0.80, 0.88),
    "interval": (0.88, 0.95),
}
# Доли от максимального пульса, если пульс покоя неизвестен
HR_MAX_PCT: dict[str, tuple[float, float]] = {
    "recovery": (0.55, 0.65),
    "easy":     (0.65, 0.75),
    "long":     (0.65, 0.77),
    "tempo":    (0.82, 0.89),
    "interval": (0.90, 0.97),
}

HISTORY_WEEKS = 8
MIN_PACE, MAX_PACE = 3.0, 15.0    # разумные границы темпа бега, мин/км
EASY_PACE_BOUNDS = (3.5, 14.0)
MAX_HR_BOUNDS = (140, 225)
REST_HR_BOUNDS = (30, 100)


def fmt_pace(p: float | None) -> str:
    """6.5 -> '6:30'."""
    if p is None:
        return "—"
    total = int(round(p * 60))
    return f"{total // 60}:{total % 60:02d}"


def riegel_time(distance_km: float, time_min: float, target_km: float) -> float:
    """Предсказанное время (мин) на target_km по результату distance_km за time_min."""
    return time_min * (target_km / distance_km) ** RIEGEL_EXPONENT


def easy_pace_from_result(distance_km: float, time_min: float) -> Optional[float]:
    """Лёгкий темп по результату на любой дистанции (через темп на 5 км)."""
    if not distance_km or not time_min or distance_km < 0.8 or distance_km > 50 or time_min <= 0:
        return None
    pace_5k = riegel_time(distance_km, time_min, 5.0) / 5.0
    easy = pace_5k * EASY_TO_5K_RATIO
    return easy if EASY_PACE_BOUNDS[0] <= easy <= EASY_PACE_BOUNDS[1] else None


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _run_pace(a) -> Optional[float]:
    pace = getattr(a, "pace_min_per_km", None)
    if not pace and getattr(a, "distance_km", 0) and getattr(a, "duration_min", 0):
        pace = a.duration_min / a.distance_km
    return pace if pace and MIN_PACE <= pace <= MAX_PACE else None


def recent_runs(activities: Iterable, now: datetime | None = None,
                weeks: int = HISTORY_WEEKS) -> list:
    """Только бег за последние weeks недель с правдоподобным темпом."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(weeks=weeks)
    out = []
    for a in activities:
        if (getattr(a, "activity_type", "run") or "run") != "run":
            continue
        if not a.date or _as_utc(a.date) < since or _as_utc(a.date) > now + timedelta(days=1):
            continue
        if (a.distance_km or 0) < 1.0 or (a.duration_min or 0) < 5 or _run_pace(a) is None:
            continue
        out.append(a)
    return out


def _history_estimate(runs: list) -> Optional[tuple[float, str, str]]:
    """(лёгкий темп, уверенность, источник) по недавним пробежкам или None."""
    if not runs:
        return None
    # Пробежка «на пределе» — почти результат: уверенность зависит от дистанции.
    hard = [a for a in runs if getattr(a, "effort", None) == "hard" and a.distance_km >= 1.5]
    if hard:
        best = max(hard, key=lambda a: a.date)
        easy = easy_pace_from_result(best.distance_km, best.duration_min)
        if easy is not None:
            return easy, ("high" if best.distance_km >= 3 else "medium"), "history_effort"
    easy_flagged = [a for a in runs if getattr(a, "effort", None) == "easy"]
    if easy_flagged:
        pace = median(_run_pace(a) for a in easy_flagged)
        return pace, "medium", "history"
    long_enough = [a for a in runs if a.distance_km >= 2.0] or runs
    pace = median(_run_pace(a) for a in long_enough)
    return pace, ("medium" if len(runs) >= 3 else "low"), "history"


@dataclass
class Zones:
    easy_pace: Optional[float]
    pace: dict[str, Optional[tuple[float, float]]]   # зона -> (быстрее, медленнее), мин/км
    pace_source: str                                  # result | history_effort | history | profile | none
    pace_confidence: str                              # high | medium | low | none
    hr: dict[str, Optional[tuple[int, int]]]          # зона -> (от, до), уд/мин
    hr_source: str                                    # profile | history | age | none
    hr_confidence: str                                # high | medium | low | none
    hr_method: str                                    # karvonen | max | none
    max_hr: Optional[int] = None
    rest_hr: Optional[int] = None

    def pace_mid(self, zone: str) -> Optional[float]:
        rng = self.pace.get(zone)
        return (rng[0] + rng[1]) / 2 if rng else None

    def to_dict(self) -> dict:
        return {
            "easy_pace": self.easy_pace,
            "pace": {k: (list(v) if v else None) for k, v in self.pace.items()},
            "pace_source": self.pace_source,
            "pace_confidence": self.pace_confidence,
            "hr": {k: (list(v) if v else None) for k, v in self.hr.items()},
            "hr_source": self.hr_source,
            "hr_confidence": self.hr_confidence,
            "hr_method": self.hr_method,
            "max_hr": self.max_hr,
            "rest_hr": self.rest_hr,
        }


def _pace_zones(easy: Optional[float]) -> dict[str, Optional[tuple[float, float]]]:
    if easy is None:
        return {k: None for k in ZONE_KEYS}
    return {k: (round(easy * lo, 2), round(easy * hi, 2)) for k, (lo, hi) in PACE_RATIOS.items()}


def _valid(value, bounds) -> Optional[int]:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if bounds[0] <= v <= bounds[1] else None


def _hr_zones(max_hr: Optional[int], rest_hr: Optional[int]):
    if not max_hr:
        return {k: None for k in ZONE_KEYS}, "none"
    if rest_hr and rest_hr < max_hr - 20:
        reserve = max_hr - rest_hr
        return {
            k: (round(rest_hr + lo * reserve), round(rest_hr + hi * reserve))
            for k, (lo, hi) in HR_RESERVE_PCT.items()
        }, "karvonen"
    return {
        k: (round(lo * max_hr), round(hi * max_hr)) for k, (lo, hi) in HR_MAX_PCT.items()
    }, "max"


def build_zones(user, activities: Iterable, now: datetime | None = None) -> Zones:
    """Зоны пользователя по профилю и истории (activities — любые, фильтруем внутри)."""
    activities = list(activities)
    runs = recent_runs(activities, now)
    hist = _history_estimate(runs)

    easy: Optional[float] = None
    source, conf = "none", "none"

    result_easy = easy_pace_from_result(
        getattr(user, "race_distance_km", None) or 0, getattr(user, "race_time_min", None) or 0
    )
    profile_easy = getattr(user, "easy_pace_min_km", None)
    if profile_easy is not None and not (EASY_PACE_BOUNDS[0] <= profile_easy <= EASY_PACE_BOUNDS[1]):
        profile_easy = None

    if result_easy is not None:
        easy, source, conf = result_easy, "result", "high"
    elif hist and hist[1] == "high":
        easy, conf, source = hist
    elif hist and hist[1] == "medium":
        easy, conf, source = hist
    elif profile_easy is not None:
        easy, source, conf = profile_easy, "profile", "medium"
    elif hist:
        easy, conf, source = hist

    # --- пульс ---
    max_hr = _valid(getattr(user, "max_hr", None), MAX_HR_BOUNDS)
    hr_source = "profile" if max_hr else "none"
    hr_conf = "high" if max_hr else "none"
    if not max_hr:
        observed = [a.max_heart_rate for a in activities if getattr(a, "max_heart_rate", None)]
        observed = [h for h in observed if MAX_HR_BOUNDS[0] <= h <= MAX_HR_BOUNDS[1]]
        if observed:
            max_hr, hr_source, hr_conf = max(observed), "history", "medium"
    if not max_hr and getattr(user, "age", None):
        max_hr = round(208 - 0.7 * user.age)      # оценка Танаки
        if MAX_HR_BOUNDS[0] <= max_hr <= MAX_HR_BOUNDS[1]:
            hr_source, hr_conf = "age", "low"
        else:
            max_hr = None
    rest_hr = _valid(getattr(user, "rest_hr", None), REST_HR_BOUNDS)
    hr, method = _hr_zones(max_hr, rest_hr)

    return Zones(
        easy_pace=easy, pace=_pace_zones(easy), pace_source=source, pace_confidence=conf,
        hr=hr, hr_source=hr_source, hr_confidence=hr_conf if max_hr else "none",
        hr_method=method, max_hr=max_hr, rest_hr=rest_hr if method == "karvonen" else None,
    )


def data_status(zones: Zones, activities: Iterable, now: datetime | None = None) -> dict:
    """Нужны ли пользователю данные для точного плана (окно «Нужны данные»)."""
    now = now or datetime.now(timezone.utc)
    runs = recent_runs(activities, now, weeks=6)
    last_days = None
    if runs:
        last = max(_as_utc(a.date) for a in runs)
        last_days = max(0, (now - last).days)
    return {
        "needs_data": zones.pace_confidence in ("none", "low"),
        "recent_runs": len(runs),
        "last_run_days_ago": last_days,
        "pace_confidence": zones.pace_confidence,
    }
