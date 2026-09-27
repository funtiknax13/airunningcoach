"""Формат тренировки плана: список отрезков (v2).

ИИ и алгоритмический планировщик выдают ОДИН И ТОТ ЖЕ формат: структура и имена
зон (easy/tempo/...), без темпов и пульса. Числа (диапазоны темпа и пульса, общая
дистанция, длительность, средний темп) считает код по зонам пользователя
(app/services/zones.py) — поэтому текст, плашки и график не могут разойтись, а
модель не может назначить темп, нереальный для этого бегуна.

Хранение: workouts.plan_structure (JSON):
    {"version": 2, "segments": [...канонические отрезки...],
     "resolved": {...числа по зонам на момент расчёта...}, "comment": "..."}
Тренировки без "version" (старые планы, легаси-структура интервалов) не трогаем.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.zones import ZONE_KEYS, Zones

VERSION = 2
WORKOUT_TYPES = ("easy", "tempo", "interval", "long", "recovery", "rest")
SEGMENT_KINDS = ("run", "warmup", "cooldown", "steady", "intervals", "run_walk", "walk")
WALK_PACE = 12.0   # мин/км — допущение для оценки дистанции ходьбы (≈5 км/ч)
COMMENT_MAX = 300

_TYPE_LABEL = {
    "easy": "Лёгкий бег", "tempo": "Темповая", "interval": "Интервалы",
    "long": "Длинная", "recovery": "Восстановление", "rest": "Отдых",
}
_DEFAULT_ZONE_BY_TYPE = {
    "easy": "easy", "long": "long", "recovery": "recovery",
    "tempo": "tempo", "interval": "interval",
}


class PlanFormatError(ValueError):
    """Ответ модели/планировщика не соответствует формату тренировки."""


# ── нормализация ────────────────────────────────────────────────────────────

def _num(raw: dict, key: str, lo: float, hi: float) -> Optional[float]:
    v = raw.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise PlanFormatError(f"{key}: не число")
    if not (lo <= v <= hi):
        raise PlanFormatError(f"{key}={v} вне диапазона {lo}..{hi}")
    return v


def _int(raw: dict, key: str, lo: int, hi: int) -> Optional[int]:
    v = _num(raw, key, lo, hi)
    return None if v is None else int(round(v))


def _zone(raw: dict, default: str) -> str:
    z = raw.get("zone") or default
    if z not in ZONE_KEYS:
        raise PlanFormatError(f"неизвестная зона {z!r}")
    return z


def normalize_segment(raw: Any, workout_type: str) -> dict:
    if not isinstance(raw, dict):
        raise PlanFormatError("отрезок должен быть объектом")
    kind = raw.get("kind")
    if kind not in SEGMENT_KINDS:
        raise PlanFormatError(f"неизвестный вид отрезка {kind!r}")
    default_zone = _DEFAULT_ZONE_BY_TYPE.get(workout_type, "easy")

    if kind in ("run", "warmup", "cooldown", "steady"):
        zone_default = {"warmup": "easy", "cooldown": "easy", "steady": "tempo",
                        "run": default_zone}[kind]
        dist = _num(raw, "distance_km", 0.2, 60)
        dur = _num(raw, "duration_min", 1, 300)
        if dist is None and dur is None:
            raise PlanFormatError(f"{kind}: нужна distance_km или duration_min")
        seg = {"kind": kind, "zone": _zone(raw, zone_default)}
        if dist is not None:
            seg["distance_km"] = round(dist, 2)
        else:
            seg["duration_min"] = round(dur, 1)
        return seg

    if kind == "intervals":
        reps = _int(raw, "reps", 1, 30)
        dist_m = _num(raw, "distance_m", 100, 5000)
        dur_s = _num(raw, "duration_s", 10, 1800)
        if reps is None or (dist_m is None and dur_s is None):
            raise PlanFormatError("intervals: нужны reps и distance_m или duration_s")
        seg: dict = {"kind": "intervals", "zone": _zone(raw, "interval"), "reps": reps}
        if dist_m is not None:
            seg["distance_m"] = int(round(dist_m))
        else:
            seg["duration_s"] = int(round(dur_s))
        rec = raw.get("recovery")
        if isinstance(rec, dict):
            r_dist = _num(rec, "distance_m", 0, 3000)
            r_dur = _num(rec, "duration_s", 0, 1800)
            r: dict = {"zone": _zone(rec, "recovery")}
            if r_dist:
                r["distance_m"] = int(round(r_dist))
            elif r_dur:
                r["duration_s"] = int(round(r_dur))
            if "distance_m" in r or "duration_s" in r:
                seg["recovery"] = r
        return seg

    if kind == "run_walk":
        reps = _int(raw, "reps", 1, 30)
        run_s = _num(raw, "run_s", 10, 3600)
        walk_s = _num(raw, "walk_s", 0, 1800)
        if reps is None or run_s is None or walk_s is None:
            raise PlanFormatError("run_walk: нужны reps, run_s, walk_s")
        return {"kind": "run_walk", "zone": _zone(raw, "easy"), "reps": reps,
                "run_s": int(round(run_s)), "walk_s": int(round(walk_s))}

    dur = _num(raw, "duration_min", 1, 180)          # walk
    if dur is None:
        raise PlanFormatError("walk: нужна duration_min")
    return {"kind": "walk", "duration_min": round(dur, 1)}


def normalize_day(raw: Any) -> dict:
    """Один день плана от модели/планировщика -> канонический вид или PlanFormatError."""
    if not isinstance(raw, dict):
        raise PlanFormatError("день плана должен быть объектом")
    wtype = raw.get("workout_type")
    if wtype not in WORKOUT_TYPES:
        raise PlanFormatError(f"неизвестный workout_type {wtype!r}")

    comment = raw.get("comment")
    comment = comment.strip()[:COMMENT_MAX] if isinstance(comment, str) and comment.strip() else None

    if wtype == "rest":
        return {"workout_type": "rest", "segments": [], "comment": comment}

    segs_raw = raw.get("segments")
    if not segs_raw and raw.get("distance_km") and wtype in ("easy", "long", "recovery"):
        # терпимость к старой форме ответа: один плоский бег
        segs_raw = [{"kind": "run", "distance_km": raw["distance_km"]}]
    if not isinstance(segs_raw, list) or not segs_raw:
        raise PlanFormatError(f"{wtype}: нет отрезков")
    if len(segs_raw) > 12:
        raise PlanFormatError("слишком много отрезков")
    segments = [normalize_segment(s, wtype) for s in segs_raw]
    return {"workout_type": wtype, "segments": segments, "comment": comment}


# ── расчёт чисел по зонам ───────────────────────────────────────────────────

def _range(zones: Zones, zone: str) -> Optional[list[float]]:
    rng = zones.pace.get(zone)
    return [rng[0], rng[1]] if rng else None


def _hr(zones: Zones, zone: str) -> Optional[list[int]]:
    rng = zones.hr.get(zone)
    return [rng[0], rng[1]] if rng else None


def _mid(rng: Optional[list[float]]) -> Optional[float]:
    return (rng[0] + rng[1]) / 2 if rng else None


def _leg(distance_km: Optional[float], duration_min: Optional[float],
         pace: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    """Достраивает (км, мин) по темпу, если известно только одно из двух."""
    if distance_km is None and duration_min is not None and pace:
        distance_km = duration_min / pace
    if duration_min is None and distance_km is not None and pace:
        duration_min = distance_km * pace
    return distance_km, duration_min


def resolve_segments(segments: list[dict], zones: Zones) -> dict:
    """Числа тренировки по зонам пользователя (см. модуль zones)."""
    out_segments = []
    tot_km: Optional[float] = 0.0
    tot_min: Optional[float] = 0.0

    def add(km, mn):
        nonlocal tot_km, tot_min
        tot_km = None if (tot_km is None or km is None) else tot_km + km
        tot_min = None if (tot_min is None or mn is None) else tot_min + mn

    for seg in segments:
        kind, zone = seg["kind"], seg.get("zone", "easy")
        pace_rng, hr_rng = _range(zones, zone), _hr(zones, zone)
        mid = _mid(pace_rng)
        item = dict(seg)

        if kind in ("run", "warmup", "cooldown", "steady"):
            km, mn = _leg(seg.get("distance_km"), seg.get("duration_min"), mid)
        elif kind == "walk":
            mn = seg["duration_min"]
            km = mn / WALK_PACE
            pace_rng, hr_rng = None, None
        elif kind == "intervals":
            reps = seg["reps"]
            rep_km, rep_min = _leg(
                seg["distance_m"] / 1000 if "distance_m" in seg else None,
                seg["duration_s"] / 60 if "duration_s" in seg else None, mid)
            km = None if rep_km is None else rep_km * reps
            mn = None if rep_min is None else rep_min * reps
            rec = seg.get("recovery")
            if rec:
                rec_rng, rec_hr = _range(zones, rec["zone"]), _hr(zones, rec["zone"])
                r_km, r_min = _leg(
                    rec["distance_m"] / 1000 if "distance_m" in rec else None,
                    rec["duration_s"] / 60 if "duration_s" in rec else None, _mid(rec_rng))
                # восстановление между повторами: reps-1 раз, но для оценки нагрузки
                # берём reps (заминка/встряска после последнего повтора)
                km = None if (km is None or r_km is None) else km + r_km * reps
                mn = None if (mn is None or r_min is None) else mn + r_min * reps
                item["recovery_pace"], item["recovery_hr"] = rec_rng, rec_hr
        else:  # run_walk
            reps = seg["reps"]
            run_km, run_min = _leg(None, seg["run_s"] / 60, mid)
            walk_min = seg["walk_s"] / 60
            walk_km = walk_min / WALK_PACE
            km = None if run_km is None else (run_km + walk_km) * reps
            mn = (seg["run_s"] / 60 + walk_min) * reps

        item["pace"], item["hr"] = pace_rng, hr_rng
        item["distance_km"] = None if km is None else round(km, 2)
        item["duration_min"] = None if mn is None else round(mn, 1)
        out_segments.append(item)
        add(km, mn)

    avg_pace = None
    if tot_km and tot_min:
        avg_pace = round(tot_min / tot_km, 2)
    return {
        "segments": out_segments,
        "distance_km": None if tot_km is None else round(tot_km, 2),
        "duration_min": None if tot_min is None else round(tot_min, 1),
        "avg_pace": avg_pace,
        "pace_confidence": zones.pace_confidence,
        "hr_confidence": zones.hr_confidence,
        "estimated": zones.pace_confidence in ("none", "low"),
    }


# ── текстовое описание (без темпов и пульса) ────────────────────────────────

def _t(seconds: int) -> str:
    return f"{seconds // 60} мин" if seconds % 60 == 0 and seconds >= 60 else f"{seconds} сек"


def _amount(seg: dict) -> str:
    if "distance_km" in seg:
        km = seg["distance_km"]
        return f"{km:g} км"
    return f"{seg['duration_min']:g} мин"


def _phrase(seg: dict) -> str:
    kind = seg["kind"]
    if kind == "warmup":
        return f"{_amount(seg)} разминка"
    if kind == "cooldown":
        return f"{_amount(seg)} заминка"
    if kind == "steady":
        return f"{_amount(seg)} в темпе"
    if kind == "run":
        return _amount(seg)
    if kind == "walk":
        return f"ходьба {seg['duration_min']:g} мин"
    if kind == "run_walk":
        return f"{seg['reps']}×(бег {_t(seg['run_s'])}, ходьба {_t(seg['walk_s'])})"
    length = f"{seg['distance_m']} м" if "distance_m" in seg else _t(seg["duration_s"])
    text = f"{seg['reps']}×{length}"
    rec = seg.get("recovery")
    if rec:
        text += ", отдых " + (f"{rec['distance_m']} м трусцой" if "distance_m" in rec else _t(rec["duration_s"]))
    return text


def describe_workout(workout_type: str, segments: list[dict]) -> str:
    label = _TYPE_LABEL.get(workout_type, workout_type)
    if workout_type == "rest" or not segments:
        return "Отдых"
    if len(segments) == 1 and segments[0]["kind"] in ("run", "steady"):
        return f"{label} {_amount(segments[0])}"
    return f"{label}: " + ", ".join(_phrase(s) for s in segments)


# ── сборка полей тренировки для записи в БД ─────────────────────────────────

def build_workout(day: dict, zones: Zones, source: str) -> dict:
    """Канонический день -> словарь для replace_upcoming_workouts."""
    wtype, segments = day["workout_type"], day["segments"]
    if wtype == "rest" or not segments:
        return {"workout_type": "rest", "description": "Отдых", "distance_km": None,
                "duration_min": None, "target_pace_min_km": None,
                "plan_structure": None, "plan_source": source}
    resolved = resolve_segments(segments, zones)
    structure = {"version": VERSION, "segments": segments, "resolved": resolved,
                 "comment": day.get("comment")}
    dist = resolved["distance_km"]
    return {
        "workout_type": wtype,
        "description": describe_workout(wtype, segments),
        "distance_km": None if dist is None else round(dist, 1),
        "duration_min": resolved["duration_min"],
        "target_pace_min_km": resolved["avg_pace"],
        "plan_structure": structure,
        "plan_source": source,
    }


def refresh_structure(plan_structure: Any, zones: Zones) -> Optional[tuple[dict, dict]]:
    """Пересчёт чисел плана по свежим зонам. None — структура не v2 (не трогаем).

    Возвращает (новая структура, поля верхнего уровня для колонок workouts)."""
    if not isinstance(plan_structure, dict) or plan_structure.get("version") != VERSION:
        return None
    segments = plan_structure.get("segments") or []
    if not segments:
        return None
    resolved = resolve_segments(segments, zones)
    new = dict(plan_structure)
    new["resolved"] = resolved
    dist = resolved["distance_km"]
    fields = {
        "distance_km": None if dist is None else round(dist, 1),
        "duration_min": resolved["duration_min"],
        "target_pace_min_km": resolved["avg_pace"],
    }
    return new, fields


def day_distance_km(day: dict, zones: Zones) -> Optional[float]:
    """Дистанция дня по зонам (для проверок объёма); None, если не определить."""
    if not day["segments"]:
        return 0.0
    return resolve_segments(day["segments"], zones)["distance_km"]


def scale_day(day: dict, factor: float) -> dict:
    """Пропорционально меняет объём дня (для ограничения недельного объёма кодом)."""
    out = dict(day)
    new_segments = []
    for seg in day["segments"]:
        s = dict(seg)
        if "distance_km" in s:
            s["distance_km"] = max(0.5, round(s["distance_km"] * factor * 2) / 2)
        elif "duration_min" in s:
            s["duration_min"] = max(1.0, round(s["duration_min"] * factor, 1))
        if s["kind"] == "intervals":
            s["reps"] = max(1, int(round(s["reps"] * factor)))
        if s["kind"] == "run_walk":
            s["reps"] = max(1, int(round(s["reps"] * factor)))
        new_segments.append(s)
    out["segments"] = new_segments
    return out
