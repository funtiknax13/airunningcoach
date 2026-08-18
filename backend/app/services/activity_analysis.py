"""
Аналитический движок тренировки — перенос откалиброванного на реальных файлах
браузерного прототипа (gpx-analyzer/index.html) на Python.

Считает поверх полноразрешённого GPS-трека (до прореживания для track_points):
- тип тренировки (бег/ходьба): файл-тег → каденс → темп, в этом порядке
- интервалы/фартлек: 1D k-means по сглаженному темпу на 50-метровых микросплитах,
  слияние коротких сегментов, слияние "просадок" внутри повтора, отсев выбросов
  через модифицированный z-score (MAD), защита от ложных срабатываний на
  ходьбе/природном дрейфе темпа
- негативный/позитивный сплит, стабильность темпа по километрам, decoupling пульса
- паузы (по разрывам GPS-сигнала и низкой скорости)

Константы ниже откалиброваны на 12+ реальных файлах Suunto в JS-прототипе — не
подбирать заново, переносить как есть. См. комментарии в gpx-analyzer/index.html
для истории калибровки каждого порога.
"""
import math
from datetime import datetime
from typing import Optional

PAUSE_SPEED_MS = 0.5
PAUSE_MIN_EVENT_S = 8
GAP_MAX_S = 120
GLITCH_SPEED_MS = 8.0
DETECT_SEG_M = 50
MIN_REL_GAP = 0.16
MAX_FAST_PACE_MINKM = 8.0
MIN_SEG_LEN_M = 100
MIN_REPS = 3
MAX_REP_PACE_CV = 0.40
Z_OUTLIER_THRESH = 3.5
MAX_REP_DIST_CV_HARD = 0.5
MAX_INNER_CV = 0.45
RUN_CADENCE_MIN_SPM = 150
WALK_CADENCE_MAX_SPM = 135


# ── Геометрия / статистика ──────────────────────────────────────────────────
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _avg(values: list) -> Optional[float]:
    v = [x for x in values if x is not None and math.isfinite(x)]
    return sum(v) / len(v) if v else None


def _median(values: list) -> Optional[float]:
    v = sorted(x for x in values if x is not None and math.isfinite(x))
    if not v:
        return None
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def _cv(values: list) -> float:
    m = _avg(values)
    if not m:
        return 1.0
    var = _avg([(x - m) ** 2 for x in values])
    return math.sqrt(var) / m


# ── Трек: кумулятивная дистанция/время, паузы, разрывы ─────────────────────
def _build_track(points: list[dict]) -> Optional[dict]:
    pts = [p for p in points if p.get("t") is not None]
    if len(pts) < 2:
        return None

    cum_dist, cum_wall, cum_moving = [0.0], [0.0], [0.0]
    dist = wall = moving = 0.0
    pause_events: list[dict] = []
    cur_pause_start, cur_pause_dur = None, 0.0
    breaks: list[int] = []

    for i in range(1, len(pts)):
        dt = (pts[i]["t"] - pts[i - 1]["t"]).total_seconds()
        if dt <= 0:
            cum_dist.append(dist); cum_wall.append(wall); cum_moving.append(moving)
            continue

        dd_raw = _haversine(pts[i - 1]["lat"], pts[i - 1]["lon"], pts[i]["lat"], pts[i]["lon"])
        implied_speed = dd_raw / dt
        is_glitch = dt <= GAP_MAX_S and implied_speed > GLITCH_SPEED_MS

        if dt > GAP_MAX_S:
            wall += dt
            breaks.append(i)
            pause_events.append({"start": pts[i - 1]["t"], "duration_sec": dt})
            cur_pause_start, cur_pause_dur = None, 0.0
        else:
            dd = min(dd_raw, GLITCH_SPEED_MS * dt) if is_glitch else dd_raw
            if is_glitch:
                breaks.append(i)
            dist += dd
            wall += dt
            v = dd / dt
            if v >= PAUSE_SPEED_MS:
                moving += dt
                if cur_pause_start is not None:
                    if cur_pause_dur >= PAUSE_MIN_EVENT_S:
                        pause_events.append({"start": cur_pause_start, "duration_sec": cur_pause_dur})
                    cur_pause_start, cur_pause_dur = None, 0.0
            else:
                if cur_pause_start is None:
                    cur_pause_start = pts[i - 1]["t"]
                cur_pause_dur += dt

        cum_dist.append(dist); cum_wall.append(wall); cum_moving.append(moving)

    if cur_pause_start is not None and cur_pause_dur >= PAUSE_MIN_EVENT_S:
        pause_events.append({"start": cur_pause_start, "duration_sec": cur_pause_dur})

    if dist < 100:
        return None

    return {
        "pts": pts, "cum_dist": cum_dist, "cum_wall": cum_wall, "cum_moving": cum_moving,
        "breaks": breaks, "total_dist": dist, "total_wall": wall, "total_moving": moving,
        "pause_events": pause_events,
    }


# ── Тип тренировки: файл-тег → каденс → темп (см. модуль docstring) ────────
def _detect_activity_type(type_text: Optional[str], track: dict) -> dict:
    if type_text:
        low = type_text.lower()
        if "walk" in low or "ходь" in low:
            return {"type": "walk", "source": "file"}
        if "run" in low or "бег" in low:
            return {"type": "run", "source": "file"}

    cads = [p["cad"] * 2 for p in track["pts"] if p.get("cad")]
    if len(cads) >= len(track["pts"]) * 0.5:
        m = _median(cads)
        if m is not None:
            if m >= RUN_CADENCE_MIN_SPM:
                return {"type": "run", "source": "cadence"}
            if m <= WALK_CADENCE_MAX_SPM:
                return {"type": "walk", "source": "cadence"}

    total_dist, total_moving = track["total_dist"], track["total_moving"]
    if total_moving > 0 and total_dist > 0:
        avg_pace = (total_moving / 60) / (total_dist / 1000)
        return {"type": "run" if avg_pace < MAX_FAST_PACE_MINKM else "walk", "source": "pace"}
    return {"type": "run", "source": "unknown"}


# ── Интерполяция / сплиты ───────────────────────────────────────────────────
def _interp_at(target_dist: float, cum_dist: list[float], arr: list[float]) -> float:
    lo, hi = 0, len(cum_dist) - 1
    if target_dist <= cum_dist[0]:
        return arr[0]
    if target_dist >= cum_dist[hi]:
        return arr[hi]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum_dist[mid] <= target_dist:
            lo = mid
        else:
            hi = mid
    d0, d1 = cum_dist[lo], cum_dist[hi]
    f = (target_dist - d0) / (d1 - d0) if d1 > d0 else 0
    return arr[lo] + (arr[hi] - arr[lo]) * f


def _avg_hr_in_range(pts: list[dict], cum_dist: list[float], from_m: float, to_m: float) -> Optional[int]:
    vals = [pts[i]["hr"] for i in range(len(pts)) if from_m <= cum_dist[i] <= to_m and pts[i].get("hr")]
    return round(sum(vals) / len(vals)) if vals else None


def _compute_splits(track: dict, seg_len_m: float) -> list[dict]:
    total = track["total_dist"]
    n = int(total // seg_len_m)
    splits = []
    prev_moving, prev_dist = 0.0, 0.0
    for k in range(1, n + 1):
        d = k * seg_len_m
        mv = _interp_at(d, track["cum_dist"], track["cum_moving"])
        dur_sec = mv - prev_moving
        seg_km = (d - prev_dist) / 1000
        pace = (dur_sec / 60) / seg_km if dur_sec > 0 and seg_km > 0 else None
        splits.append({
            "idx": k, "from_m": prev_dist, "to_m": d, "dur_sec": dur_sec, "pace_min_km": pace,
            "avg_hr": _avg_hr_in_range(track["pts"], track["cum_dist"], prev_dist, d),
        })
        prev_moving, prev_dist = mv, d

    if total - prev_dist > 20:
        mv2 = track["total_moving"]
        dur_sec2 = mv2 - prev_moving
        seg_km2 = (total - prev_dist) / 1000
        splits.append({
            "idx": n + 1, "from_m": prev_dist, "to_m": total, "dur_sec": dur_sec2,
            "pace_min_km": (dur_sec2 / 60) / seg_km2 if dur_sec2 > 0 and seg_km2 > 0 else None,
            "avg_hr": _avg_hr_in_range(track["pts"], track["cum_dist"], prev_dist, total),
            "partial": True,
        })
    return splits


# ── Детекция интервалов/фартлека ────────────────────────────────────────────
def _merge_short_segments(segs: list[dict], min_len: int) -> list[dict]:
    segs = [dict(s) for s in segs]
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i in range(len(segs)):
            length = segs[i]["to"] - segs[i]["from"] + 1
            if length < min_len:
                prev = segs[i - 1] if i > 0 else None
                nxt = segs[i + 1] if i + 1 < len(segs) else None
                if prev and nxt:
                    target = nxt if (nxt["to"] - nxt["from"]) >= (prev["to"] - prev["from"]) else prev
                    target["from"] = min(target["from"], segs[i]["from"])
                    target["to"] = max(target["to"], segs[i]["to"])
                elif prev:
                    prev["to"] = segs[i]["to"]
                elif nxt:
                    nxt["from"] = segs[i]["from"]
                else:
                    break
                del segs[i]
                changed = True
                break

    collapsed = []
    for s in segs:
        last = collapsed[-1] if collapsed else None
        if last and last["cls"] == s["cls"] and s["from"] == last["to"] + 1:
            last["to"] = s["to"]
        else:
            collapsed.append({"cls": s["cls"], "from": s["from"], "to": s["to"]})
    return collapsed


def _build_segment_stats(splits: list[dict], seg: dict) -> dict:
    sl = splits[seg["from"]:seg["to"] + 1]
    from_m, to_m = sl[0]["from_m"], sl[-1]["to_m"]
    dur_sec = sum(s.get("dur_sec") or 0 for s in sl)
    dist_m = to_m - from_m
    pace = (dur_sec / 60) / (dist_m / 1000) if dur_sec > 0 and dist_m > 0 else None
    hrs = [s["avg_hr"] for s in sl if s.get("avg_hr") is not None]
    inner_paces = [s["pace_min_km"] for s in sl if s.get("pace_min_km") is not None]
    return {
        "cls": seg["cls"], "from_m": from_m, "to_m": to_m, "dist_m": dist_m, "dur_sec": dur_sec,
        "pace_min_km": pace, "avg_hr": round(_avg(hrs)) if hrs else None,
        "inner_cv": _cv(inner_paces) if len(inner_paces) > 1 else 0.0,
    }


def _merge_shallow_dips(segs: list[dict], splits: list[dict], fast_c: float, slow_c: float,
                         fast_hr: Optional[float], slow_hr: Optional[float]) -> list[dict]:
    segs = [dict(s) for s in segs]
    use_hr = fast_hr is not None and slow_hr is not None and abs(fast_hr - slow_hr) > 3
    changed = True
    while changed:
        changed = False
        for i in range(1, len(segs) - 1):
            prev, cur, nxt = segs[i - 1], segs[i], segs[i + 1]
            if cur["cls"] == "slow" and prev["cls"] == "fast" and nxt["cls"] == "fast":
                stat = _build_segment_stats(splits, cur)
                prev_stat = _build_segment_stats(splits, prev)
                next_stat = _build_segment_stats(splits, nxt)
                is_short = stat["dist_m"] < 0.4 * ((prev_stat["dist_m"] + next_stat["dist_m"]) / 2)
                is_dip = False
                if is_short:
                    if use_hr and stat["avg_hr"] is not None:
                        is_dip = abs(stat["avg_hr"] - fast_hr) < abs(stat["avg_hr"] - slow_hr)
                    elif stat["pace_min_km"] is not None:
                        is_dip = abs(stat["pace_min_km"] - fast_c) < abs(stat["pace_min_km"] - slow_c)
                if is_dip:
                    segs[i - 1] = {"cls": "fast", "from": prev["from"], "to": nxt["to"]}
                    del segs[i:i + 2]
                    changed = True
                    break
    return segs


def _detect_intervals(track: dict, activity_type: dict) -> Optional[dict]:
    splits = _compute_splits(track, DETECT_SEG_M)
    valid_count = sum(1 for s in splits if s["pace_min_km"] is not None)
    if valid_count < 8:
        return None

    smoothed = []
    for i, s in enumerate(splits):
        win = []
        if s["pace_min_km"] is not None:
            win.append(s["pace_min_km"])
        if i > 0 and splits[i - 1]["pace_min_km"] is not None:
            win.append(splits[i - 1]["pace_min_km"])
        if i + 1 < len(splits) and splits[i + 1]["pace_min_km"] is not None:
            win.append(splits[i + 1]["pace_min_km"])
        smoothed.append(_avg(win) if win else None)

    vals = [v for v in smoothed if v is not None]
    if len(vals) < 8:
        return None

    c0, c1 = min(vals), max(vals)
    for _ in range(25):
        s0 = n0 = s1 = n1 = 0
        for v in vals:
            if abs(v - c0) <= abs(v - c1):
                s0 += v; n0 += 1
            else:
                s1 += v; n1 += 1
        if n0:
            c0 = s0 / n0
        if n1:
            c1 = s1 / n1
    fast_c, slow_c = min(c0, c1), max(c0, c1)

    confident_run = activity_type and activity_type["type"] == "run" and activity_type["source"] != "pace"
    if fast_c >= MAX_FAST_PACE_MINKM and not confident_run:
        return None
    if slow_c <= 0 or (slow_c - fast_c) / slow_c < MIN_REL_GAP:
        return None

    mid = (fast_c + slow_c) / 2
    cls = [None if v is None else ("fast" if v <= mid else "slow") for v in smoothed]

    segs = []
    cur_cls, cur_start = None, 0
    for i, c in enumerate(cls):
        if c is None:
            continue
        if cur_cls is None:
            cur_cls, cur_start = c, i
            continue
        if c != cur_cls:
            segs.append({"cls": cur_cls, "from": cur_start, "to": i - 1})
            cur_cls, cur_start = c, i
    if cur_cls is not None:
        segs.append({"cls": cur_cls, "from": cur_start, "to": len(cls) - 1})

    min_len_splits = max(2, round(MIN_SEG_LEN_M / DETECT_SEG_M))
    segs = _merge_short_segments(segs, min_len_splits)

    pre_built = [_build_segment_stats(splits, seg) for seg in segs]
    fast_hrs = [s["avg_hr"] for s in pre_built if s["cls"] == "fast" and s["avg_hr"] is not None]
    slow_hrs = [s["avg_hr"] for s in pre_built if s["cls"] == "slow" and s["avg_hr"] is not None]
    fast_hr = _avg(fast_hrs) if fast_hrs else None
    slow_hr = _avg(slow_hrs) if slow_hrs else None
    segs = _merge_shallow_dips(segs, splits, fast_c, slow_c, fast_hr, slow_hr)
    if len(segs) < 3:
        return None

    built = [_build_segment_stats(splits, seg) for seg in segs]
    fast_segs = [s for s in built if s["cls"] == "fast"]
    if len(fast_segs) < MIN_REPS:
        return None

    rep_dists_all = [s["dist_m"] for s in fast_segs]
    median_rep_dist = _median(rep_dists_all)
    abs_devs = [abs(d - median_rep_dist) for d in rep_dists_all]
    mad_dist = _median(abs_devs)
    mad_scale = mad_dist if mad_dist and mad_dist > 0 else (_avg(abs_devs) or 1)

    def is_plateau_rep(s: dict) -> bool:
        z = 0.6745 * (s["dist_m"] - median_rep_dist) / mad_scale
        return z > -Z_OUTLIER_THRESH and s["inner_cv"] <= MAX_INNER_CV

    main_reps = [s for s in fast_segs if is_plateau_rep(s)]
    extra_reps = [s for s in fast_segs if not is_plateau_rep(s)]
    if len(main_reps) < MIN_REPS:
        return None

    if _cv([s["pace_min_km"] for s in main_reps]) > MAX_REP_PACE_CV:
        return None

    warmup = built[0] if built[0]["cls"] == "slow" and built[0]["dist_m"] >= 300 else None
    cooldown = (built[-1] if built[-1]["cls"] == "slow" and built[-1]["dist_m"] >= 300 and len(built) > 1
                else None)

    recoveries = []
    for ri in range(len(main_reps) - 1):
        idx_a, idx_b = built.index(main_reps[ri]), built.index(main_reps[ri + 1])
        if idx_b == idx_a + 2 and built[idx_a + 1]["cls"] == "slow":
            recoveries.append(built[idx_a + 1])

    rep_dists = [s["dist_m"] for s in main_reps]
    rep_paces = [s["pace_min_km"] for s in main_reps]
    dist_cv, pace_cv = _cv(rep_dists), _cv(rep_paces)
    is_clean = dist_cv < 0.28 and pace_cv < 0.15

    if dist_cv > MAX_REP_DIST_CV_HARD:
        return None

    return {
        "segments": built, "reps": main_reps, "extra_reps": extra_reps, "recoveries": recoveries,
        "warmup": warmup, "cooldown": cooldown, "kind": "intervals" if is_clean else "fartlek",
    }


# ── Доп. метрики ─────────────────────────────────────────────────────────────
def _negative_split(km_splits: list[dict]) -> Optional[dict]:
    v = [s for s in km_splits if s["pace_min_km"] is not None and not s.get("partial")]
    if len(v) < 4:
        return None
    half = len(v) // 2
    a1 = _avg([s["pace_min_km"] for s in v[:half]])
    a2 = _avg([s["pace_min_km"] for s in v[half:]])
    if not a1 or not a2:
        return None
    return {"first_avg": a1, "second_avg": a2, "diff_pct": (a2 - a1) / a1 * 100}


def _pace_consistency(km_splits: list[dict]) -> Optional[float]:
    v = [s["pace_min_km"] for s in km_splits if s["pace_min_km"] is not None and not s.get("partial")]
    return _cv(v) if len(v) >= 3 else None


def _hr_decoupling(track: dict) -> Optional[float]:
    hrs = [p for p in track["pts"] if p.get("hr")]
    if len(hrs) < 20 or track["total_moving"] < 20 * 60:
        return None
    total_dist = track["total_dist"]
    half = total_dist / 2
    pts, cum_dist, cum_moving = track["pts"], track["cum_dist"], track["cum_moving"]

    def eff_at(from_d: float, to_d: float) -> Optional[float]:
        hrs_seg = [pts[i]["hr"] for i in range(len(pts)) if from_d <= cum_dist[i] <= to_d and pts[i].get("hr")]
        if not hrs_seg:
            return None
        mv0 = _interp_at(from_d, cum_dist, cum_moving)
        mv1 = _interp_at(to_d, cum_dist, cum_moving)
        dur_min, dist_km = (mv1 - mv0) / 60, (to_d - from_d) / 1000
        if dur_min <= 0 or dist_km <= 0:
            return None
        speed_kmh = dist_km / (dur_min / 60)
        return speed_kmh / _avg(hrs_seg)

    e1, e2 = eff_at(0, half), eff_at(half, total_dist)
    if not e1 or not e2:
        return None
    return (e1 - e2) / e1 * 100


# ── Точка входа ──────────────────────────────────────────────────────────────
def compute_analysis(points: list[dict], type_text: Optional[str] = None) -> Optional[dict]:
    """points: [{lat, lon, t (datetime|None), ele, hr, cad}], cad — одна нога (как в GPX).

    Возвращает компактный словарь фактов (не сырой трек — он уже хранится отдельно
    в laps/splits/track_points) либо None, если данных недостаточно для анализа —
    вызывающий код должен воспринимать это как «анализ недоступен», не как ошибку."""
    track = _build_track(points)
    if track is None:
        return None

    activity_type = _detect_activity_type(type_text, track)
    km_splits = _compute_splits(track, 1000)
    intervals = _detect_intervals(track, activity_type)
    negative_split = _negative_split(km_splits)
    pace_consistency = _pace_consistency(km_splits)
    hr_decoupling = _hr_decoupling(track)

    return {
        "activity_type": activity_type,
        "intervals": intervals,
        "negative_split": negative_split,
        "pace_consistency": pace_consistency,
        "hr_decoupling": hr_decoupling,
        "pauses": {
            "count": len(track["pause_events"]),
            "total_sec": track["total_wall"] - track["total_moving"],
        },
    }
