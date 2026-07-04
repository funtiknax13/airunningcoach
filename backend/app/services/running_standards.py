# app/services/running_standards.py
"""
Нормативы спортивных разрядов ЕВСК по бегу — только дистанции, реалистичные
для GPS-трекинга (без коротких треков и юношеских разрядов — та часть таблицы
живёт в публичном калькуляторе /tools/normativy-bega/).

Источник данных — тот же датасет, что извлечён и провалидирован для
frontend-v2/public/tools/normativy-bega/index.html.
"""

STANDARD_DISTANCES = [
    {"key": "1000m",         "km": 1.0,     "label": "1 км"},
    {"key": "1500m",         "km": 1.5,     "label": "1500 м"},
    {"key": "mile",          "km": 1.60934, "label": "1 миля"},
    {"key": "3000m",         "km": 3.0,     "label": "3000 м"},
    {"key": "5000m",         "km": 5.0,     "label": "5 км"},
    {"key": "10000m",        "km": 10.0,    "label": "10 км"},
    {"key": "15km",          "km": 15.0,    "label": "15 км"},
    {"key": "half_marathon", "km": 21.0975, "label": "Полумарафон"},
    {"key": "marathon",      "km": 42.195,  "label": "Марафон"},
]

RANK_ORDER = ["msmk", "ms", "kms", "r1", "r2", "r3"]
RANK_LABELS = {
    "msmk": "МСМК", "ms": "МС", "kms": "КМС",
    "r1": "I разряд", "r2": "II разряд", "r3": "III разряд",
}

DISTANCE_TOLERANCE = 0.03  # ±3% — GPS-трек засчитывается как попытка на эту дистанцию

# Пороги в секундах (мужской автохронометраж, круг 400м; шоссе — как в первоисточнике)
NORMS: dict[str, dict[str, dict[str, float | None]]] = {
    "male": {
        "1000m":         {"msmk": None,   "ms": 142.24, "kms": 148.24, "r1": 157.24, "r2": 169.24, "r3": 183.24},
        "1500m":         {"msmk": 217.0,  "ms": 226.1,  "kms": 236.94, "r1": 249.94, "r2": 265.74, "r3": 285.24},
        "mile":          {"msmk": None,   "ms": 243.0,  "kms": 258.74, "r1": 270.24, "r2": 292.24, "r3": 319.24},
        "3000m":         {"msmk": 472.24, "ms": 484.24, "kms": 510.24, "r1": 540.24, "r2": 580.24, "r3": 630.24},
        "5000m":         {"msmk": 807.0,  "ms": 846.0,  "kms": 890.24, "r1": 955.24, "r2": 1020.24, "r3": 1085.24},
        "10000m":        {"msmk": 1680.0, "ms": 1760.0, "kms": 1870.24, "r1": 2000.24, "r2": 2150.24, "r3": 2320.24},
        "15km":          {"msmk": None,   "ms": None,   "kms": 2940.0, "r1": 3120.0, "r2": 3360.0, "r3": 3600.0},
        "half_marathon": {"msmk": 3690.0, "ms": 3900.0, "kms": 4230.0, "r1": 4560.0, "r2": 4890.0, "r3": 5280.0},
        "marathon":      {"msmk": 7920.0, "ms": 8400.0, "kms": 9000.0, "r1": 9600.0, "r2": 10200.0, "r3": 11400.0},
    },
    "female": {
        "1000m":         {"msmk": None,   "ms": 165.24, "kms": 176.24, "r1": 187.24, "r2": 201.24, "r3": 217.24},
        "1500m":         {"msmk": 245.5,  "ms": 258.24, "kms": 278.24, "r1": 297.24, "r2": 319.24, "r3": 345.24},
        "mile":          {"msmk": None,   "ms": 279.24, "kms": 298.24, "r1": 320.24, "r2": 344.24, "r3": 373.24},
        "3000m":         {"msmk": 530.24, "ms": 553.24, "kms": 600.24, "r1": 653.24, "r2": 713.24, "r3": 778.24},
        "5000m":         {"msmk": 920.24, "ms": 965.24, "kms": 1040.24, "r1": 1125.24, "r2": 1220.24, "r3": 1325.24},
        "10000m":        {"msmk": 1910.24, "ms": 2028.24, "kms": 2220.24, "r1": 2400.24, "r2": 2620.24, "r3": 2870.24},
        "15km":          {"msmk": None,    "ms": None,    "kms": 3540.0, "r1": 3720.0, "r2": 4020.0, "r3": 4380.0},
        "half_marathon": {"msmk": 4260.0,  "ms": 4540.0,  "kms": 5100.0, "r1": 5670.0, "r2": 6270.0, "r3": 6900.0},
        "marathon":      {"msmk": 9000.0,  "ms": 9600.0,  "kms": 10800.0, "r1": 12120.0, "r2": 13680.0, "r3": 15000.0},
    },
}

_DISTANCE_BY_KEY = {d["key"]: d for d in STANDARD_DISTANCES}


def match_distance(distance_km: float) -> dict | None:
    """Ближайшая стандартная дистанция в пределах ±3%, иначе None."""
    best = None
    best_rel_diff = None
    for d in STANDARD_DISTANCES:
        rel_diff = abs(distance_km - d["km"]) / d["km"]
        if rel_diff <= DISTANCE_TOLERANCE and (best_rel_diff is None or rel_diff < best_rel_diff):
            best = d
            best_rel_diff = rel_diff
    return best


def evaluate_rank(gender: str, distance_key: str, time_sec: float) -> str | None:
    """Лучший разряд (от МСМК к III), порог которого побит временем. None — норматив не выполнен."""
    thresholds = NORMS.get(gender, {}).get(distance_key)
    if not thresholds:
        return None
    for rank in RANK_ORDER:
        threshold = thresholds.get(rank)
        if threshold is not None and time_sec <= threshold:
            return rank
    return None


def next_rank_gap(gender: str, distance_key: str, time_sec: float, achieved_rank: str | None) -> tuple[str | None, float | None]:
    """Следующий (лучший) разряд и сколько секунд до него не хватает."""
    thresholds = NORMS.get(gender, {}).get(distance_key)
    if not thresholds:
        return None, None
    order = RANK_ORDER
    start_idx = order.index(achieved_rank) if achieved_rank in order else len(order)
    for i in range(start_idx - 1, -1, -1):
        threshold = thresholds.get(order[i])
        if threshold is not None:
            return order[i], time_sec - threshold
    return None, None
