"""
Парсер GPX-файлов (Garmin, Suunto, Polar, Coros и др.)

Извлекает:
- дистанцию (Haversine), время, средний/макс пульс, каденс, набор высоты
- сплиты по километрам
- сегменты трека как отдельные круги (если несколько trkseg)
- прореженный GPS-трек (~1 точка / 10 сек, не более 300 точек)
"""
import math
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from typing import Optional

_NS_HR  = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
_NS_CAD = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Расстояние в метрах."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _parse_time(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _get_ns(root) -> str:
    return root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""


def _find_ext(trkpt, prefix: str, *tags):
    """Ищет значение в extensions по нескольким возможным тегам."""
    for tag in tags:
        el = trkpt.find(f".//{{{_NS_HR}}}{tag}")
        if el is not None and el.text:
            try: return int(el.text.strip())
            except ValueError: pass
        el = trkpt.find(f".//{prefix}{tag}")
        if el is not None and el.text:
            try: return int(el.text.strip())
            except ValueError: pass
    return None


def _compute_splits(points: list) -> list:
    """Вычисляет сплиты по километрам из точек трека."""
    splits = []
    km_start_idx = 0
    km_dist = 0.0
    km_num = 1
    km_hrs = []

    for i in range(1, len(points)):
        p, prev = points[i], points[i-1]
        seg = _haversine(prev["lat"], prev["lon"], p["lat"], p["lon"])
        km_dist += seg / 1000

        if p.get("hr"): km_hrs.append(p["hr"])

        if km_dist >= 1.0:
            # Рассчитываем темп для этого км
            t_start = points[km_start_idx].get("time")
            t_end   = p.get("time")
            if t_start and t_end:
                pace = (t_end - t_start).total_seconds() / 60 / km_dist
                splits.append({
                    "km":     km_num,
                    "pace":   round(pace, 2),
                    "avg_hr": round(sum(km_hrs)/len(km_hrs)) if km_hrs else None,
                })
            km_num    += 1
            km_start_idx = i
            km_dist = 0.0
            km_hrs  = []

    return splits


def _downsample(points: list, max_points: int = 300, interval_sec: int = 10) -> list:
    """Прореживаем трек: оставляем ~1 точку каждые interval_sec секунд, не более max_points."""
    if not points: return []
    t0 = points[0].get("time")
    if not t0: return points[::max(1, len(points)//max_points)][:max_points]

    result = [points[0]]
    last_t = t0
    for p in points[1:]:
        t = p.get("time")
        if t and (t - last_t).total_seconds() >= interval_sec:
            result.append(p)
            last_t = t
        if len(result) >= max_points:
            break
    return result


def parse_gpx(content: bytes) -> dict:
    """
    Парсит GPX и возвращает полный словарь с деталями тренировки.
    """
    root = ET.fromstring(content)
    ns   = _get_ns(root)
    px   = f"{{{ns}}}" if ns else ""

    all_points = []   # все точки со всех сегментов
    segment_groups = []  # точки по сегментам (для кругов)

    for trkseg in root.iter(f"{px}trkseg"):
        seg_pts = []
        for trkpt in trkseg.iter(f"{px}trkpt"):
            lat = trkpt.get("lat"); lon = trkpt.get("lon")
            if lat is None or lon is None: continue

            time_el = trkpt.find(f"{px}time")
            t = _parse_time(time_el.text.strip()) if time_el is not None and time_el.text else None

            ele_el = trkpt.find(f"{px}ele")
            ele = float(ele_el.text) if ele_el is not None and ele_el.text else None

            hr  = _find_ext(trkpt, px, "hr")
            cad = _find_ext(trkpt, px, "cad", "cadence", "RunCadence")

            seg_pts.append({"lat": float(lat), "lon": float(lon),
                            "time": t, "ele": ele, "hr": hr, "cad": cad})
        if seg_pts:
            segment_groups.append(seg_pts)
            all_points.extend(seg_pts)

    if len(all_points) < 2:
        raise ValueError("GPX файл не содержит трека с точками.")

    # ── Основные метрики ──────────────────────────────────────────────────────
    total_m = sum(
        _haversine(all_points[i]["lat"], all_points[i]["lon"],
                   all_points[i+1]["lat"], all_points[i+1]["lon"])
        for i in range(len(all_points)-1)
    )
    distance_km = round(total_m / 1000, 3)
    if distance_km < 0.1:
        raise ValueError("Дистанция слишком маленькая (< 100 м).")

    times = [p["time"] for p in all_points if p["time"] is not None]
    if len(times) < 2:
        raise ValueError("GPX файл не содержит временных меток.")
    duration_min = round((times[-1] - times[0]).total_seconds() / 60, 2)
    if duration_min <= 0:
        raise ValueError("Длительность трека равна нулю.")

    # Пульс
    hrs = [p["hr"] for p in all_points if p["hr"] and p["hr"] > 0]
    avg_hr = round(sum(hrs) / len(hrs)) if hrs else None
    max_hr = max(hrs) if hrs else None

    # Каденс (шаги в минуту; GPX хранит одну ногу → ×2)
    cads = [p["cad"] for p in all_points if p["cad"] and p["cad"] > 0]
    avg_cad = round(sum(cads) / len(cads) * 2) if cads else None  # ×2 для обеих ног

    # Набор высоты
    eles = [p["ele"] for p in all_points if p["ele"] is not None]
    elevation_gain = None
    if len(eles) >= 2:
        gain = sum(max(0, eles[i+1] - eles[i]) for i in range(len(eles)-1))
        elevation_gain = round(gain, 1)

    # ── Сплиты по км ─────────────────────────────────────────────────────────
    splits = _compute_splits(all_points)

    # ── Круги = сегменты трека (если их > 1) ─────────────────────────────────
    laps = []
    for i, seg in enumerate(segment_groups):
        if len(seg) < 2: continue
        seg_dist = sum(
            _haversine(seg[j]["lat"], seg[j]["lon"], seg[j+1]["lat"], seg[j+1]["lon"])
            for j in range(len(seg)-1)
        ) / 1000
        seg_times = [p["time"] for p in seg if p["time"]]
        seg_dur = (seg_times[-1] - seg_times[0]).total_seconds() / 60 if len(seg_times) >= 2 else None
        seg_hrs  = [p["hr"] for p in seg if p["hr"] and p["hr"] > 0]
        laps.append({
            "num":      i + 1,
            "dist_km":  round(seg_dist, 3),
            "dur_min":  round(seg_dur, 2) if seg_dur else None,
            "pace":     round(seg_dur / seg_dist, 2) if seg_dur and seg_dist > 0 else None,
            "avg_hr":   round(sum(seg_hrs)/len(seg_hrs)) if seg_hrs else None,
            "max_hr":   max(seg_hrs) if seg_hrs else None,
        })

    # ── Прореженный трек ─────────────────────────────────────────────────────
    sampled = _downsample(all_points)
    t0 = times[0]
    cumulative_dist = 0.0
    track_points = []
    prev = None
    for p in sampled:
        if prev:
            cumulative_dist += _haversine(prev["lat"], prev["lon"], p["lat"], p["lon"])
        pt = {
            "t":    int((p["time"] - t0).total_seconds()) if p["time"] else None,
            "lat":  round(p["lat"], 6),
            "lon":  round(p["lon"], 6),
            "dist": round(cumulative_dist / 1000, 3),
        }
        if p["ele"] is not None: pt["ele"] = round(p["ele"], 1)
        if p["hr"]:              pt["hr"]  = p["hr"]
        track_points.append(pt)
        prev = p

    return {
        "date":           times[0],
        "distance_km":    distance_km,
        "duration_min":   duration_min,
        "avg_heart_rate": avg_hr,
        "max_heart_rate": max_hr,
        "avg_cadence":    avg_cad,
        "elevation_gain": elevation_gain,
        "laps":           laps if len(laps) > 1 else None,
        "splits":         splits if splits else None,
        "track_points":   track_points if track_points else None,
        "source":         "gpx",
    }
