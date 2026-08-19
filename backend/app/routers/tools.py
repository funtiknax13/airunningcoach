# app/routers/tools.py
"""Публичные бесплатные инструменты (лид-магниты) — без авторизации."""
import math
import time

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.services.gpx_parser import parse_gpx
from app.services.fit_parser import parse_fit

router = APIRouter(prefix="/tools", tags=["tools"])

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 МБ — с запасом для сверхдлинных (100+ км) тренировок
RATE_LIMIT = 20        # запросов
RATE_WINDOW = 3600.0   # за час, на IP

# Простой rate-limit в памяти процесса — достаточно для публичного MVP-инструмента
# без БД и без внешних зависимостей (Redis и т.п. пока не нужны).
_hits: dict[str, list[float]] = {}


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Слишком много запросов. Попробуйте через час.")
    recent.append(now)
    _hits[ip] = recent


@router.post("/analyze")
async def analyze_public_activity(request: Request, file: UploadFile = File(...)):
    """Разбор GPX/FIT-файла без сохранения — для публичного анализатора пробежек."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (максимум 15 МБ)")

    filename = (file.filename or "").lower()
    if not (filename.endswith(".gpx") or filename.endswith(".fit")):
        raise HTTPException(status_code=400, detail="Поддерживаются только .gpx и .fit файлы")

    try:
        data = parse_gpx(content) if filename.endswith(".gpx") else parse_fit(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        # Битый/нечитаемый файл (невалидный XML, повреждённый бинарник FIT и т.п.) —
        # это ошибка пользовательского ввода, а не сервера, отдаём чистый 422.
        raise HTTPException(status_code=422, detail="Не удалось прочитать файл. Убедитесь, что это корректный GPX или FIT.")

    avg_pace = round(data["duration_min"] / data["distance_km"], 2) if data["distance_km"] else None

    return {
        "distance_km":    data["distance_km"],
        "duration_min":   data["duration_min"],
        "avg_pace":       avg_pace,
        "avg_heart_rate": data["avg_heart_rate"],
        "max_heart_rate": data["max_heart_rate"],
        "avg_cadence":    data["avg_cadence"],
        "elevation_gain": data["elevation_gain"],
        "splits":         data["splits"],
        "activity_type":  data["activity_type"],
        # Трек и разбор (интервалы, тип бег/ходьба, сплит, decoupling) — для карты,
        # графиков и нарратива на публичной странице анализатора. Ничего не
        # сохраняется на сервере, только отдаётся в этом ответе.
        "track_points":   data["track_points"],
        "analysis":       data["analysis"],
    }


# ── Генератор маршрутов (OpenRouteService через серверный ключ) ─────────────────
ORS_URL = "https://api.openrouteservice.org/v2/directions/"
ORS_MAX_M = 100000          # потолок длины маршрута у бесплатного ORS (100 км)
_LOOP_TOL = 0.05            # целимся в ±5% по длине кольца
_LOOP_TRIES = 5            # попыток коррекции длины
_LOOP_POINTS = 4
_EARTH_R = 6_371_000


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return _EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2, dlam = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlam)
    return math.degrees(math.atan2(y, x)) % 360


def _offset_point(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    br, lat1, lon1 = math.radians(bearing_deg), math.radians(lat), math.radians(lon)
    d_r = dist_m / _EARTH_R
    lat2 = math.asin(math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(br))
    lon2 = lon1 + math.atan2(math.sin(br) * math.sin(d_r) * math.cos(lat1),
                              math.cos(d_r) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


class Point(BaseModel):
    lat: float
    lng: float


class RouteRequest(BaseModel):
    mode: str = "run"           # run | walk | bike
    terrain: str = "city"       # city | nature
    no_steps: bool = False
    km: float = 10.0
    seed: int = 1
    start: Point
    finish: Optional[Point] = None


def _profile(mode: str, terrain: str) -> str:
    """«Тропы и парки» → природные профили (тропы/парки), «город» → уличные."""
    if mode == "bike":
        return "cycling-mountain" if terrain == "nature" else "cycling-regular"
    return "foot-hiking" if terrain == "nature" else "foot-walking"


@router.post("/route")
async def generate_route(req: RouteRequest, request: Request):
    """Строит маршрут через OpenRouteService. Ключ ORS живёт на сервере, поэтому в
    браузер не утекает; для колец здесь же выполняется замкнутая коррекция длины
    (round_trip сильно промахивается по длине и зависит от seed)."""
    if not settings.ORS_API_KEY:
        raise HTTPException(status_code=503, detail="Генерация маршрутов пока недоступна.")
    _check_rate_limit(request.client.host if request.client else "unknown")

    if req.mode not in ("run", "walk", "bike"):
        raise HTTPException(status_code=400, detail="Неверный тип активности.")
    km = max(1.0, min(100.0, float(req.km)))
    profile = _profile(req.mode, req.terrain)
    avoid = ["steps"] if req.no_steps else None
    headers = {"Authorization": settings.ORS_API_KEY, "Content-Type": "application/json"}
    loop = req.finish is None

    async with httpx.AsyncClient(timeout=45.0) as client:
        async def call(body: dict) -> dict:
            try:
                r = await client.post(ORS_URL + profile + "/geojson", headers=headers, json=body)
            except httpx.HTTPError:
                raise HTTPException(status_code=502, detail="Сервис маршрутов недоступен, попробуйте позже.")
            data = r.json() if r.content else {}
            if r.status_code >= 400 or not data.get("features"):
                err = data.get("error")
                msg = err.get("message") if isinstance(err, dict) else (err or "Не удалось построить маршрут.")
                # 4xx от ORS почти всегда про параметры (слишком длинно и т.п.) → 400 пользователю
                raise HTTPException(status_code=400 if r.status_code < 500 else 502, detail=msg)
            return data["features"][0]

        if not loop:
            async def route_via(vias: list[tuple[float, float]]) -> dict:
                coords = [[req.start.lng, req.start.lat]]
                coords += [[v[1], v[0]] for v in vias]
                coords.append([req.finish.lng, req.finish.lat])
                body = {"coordinates": coords, "elevation": True, "instructions": False}
                if avoid:
                    body["options"] = {"avoid_features": avoid}
                return await call(body)

            direct_dist = _haversine_m(req.start.lat, req.start.lng, req.finish.lat, req.finish.lng)
            target = km * 1000

            # Раньше старт+финиш всегда давали кратчайший путь между ними, полностью
            # игнорируя заданную дистанцию — если цель короче прямой (или точки почти
            # совпали), тянуть уже некуда, отдаём прямой маршрут как есть.
            if target <= direct_dist * 1.05 or direct_dist < 50:
                feat = await route_via([])
            else:
                # Первая версия сдвигала обе via-точки на 28%/72% хорды старт-финиш.
                # Это разваливалось именно в самом частом случае — старт и финиш
                # близко друг к другу, а цель намного длиннее прямой (почти кольцо
                # с чуть разнесёнными концами): 28%/72% тоже оказываются рядом на
                # крошечной хорде, и после одинакового смещения «наружу» обе точки
                # остаются в паре десятков метров друг от друга — «туда» и «обратно»
                # снова идут по одному коридору. Разносим via-точки не вдоль хорды
                # (она может быть нулевой), а вдоль радиуса петли — одна ближе к
                # стороне старта, другая ближе к стороне финиша, — так расстояние
                # между ними растёт вместе с петлёй, а не с расстоянием старт-финиш.
                bearing = _bearing_deg(req.start.lat, req.start.lng, req.finish.lat, req.finish.lng)
                side = 1 if (req.seed % 2 == 0) else -1
                jitter = (req.seed % 41) - 20  # ±20° для разнообразия вариантов на тот же seed-чёт/нечёт
                out_bearing = (bearing + side * 90 + jitter) % 360
                mid_lat = (req.start.lat + req.finish.lat) / 2
                mid_lon = (req.start.lng + req.finish.lng) / 2

                half, half_target = direct_dist / 2, target / 2
                radius = math.sqrt(max(0.0, half_target ** 2 - half ** 2))
                best, best_err = None, float("inf")
                for _ in range(_LOOP_TRIES):
                    r = max(60.0, radius)
                    width = r * 0.8  # ширина петли — доля радиуса, не хорды
                    center_lat, center_lon = _offset_point(mid_lat, mid_lon, out_bearing, r)
                    via1 = _offset_point(center_lat, center_lon, (bearing + 180) % 360, width / 2)  # к стороне старта
                    via2 = _offset_point(center_lat, center_lon, bearing, width / 2)                # к стороне финиша
                    feat = await route_via([via1, via2])
                    act = (feat["properties"].get("summary") or {}).get("distance") or 0
                    err = abs(act - target) / target if target else 1
                    if err < best_err:
                        best_err, best = err, feat
                    if err <= _LOOP_TOL or not act:
                        break
                    radius = max(60.0, min(target * 0.7, radius * (target / act) if act else radius * 1.3))
                feat = best
        else:
            target = km * 1000
            reqlen = target
            best = None
            best_err = float("inf")
            for _ in range(_LOOP_TRIES):
                opts = {"round_trip": {"length": min(ORS_MAX_M, round(reqlen)), "points": _LOOP_POINTS, "seed": req.seed}}
                if avoid:
                    opts["avoid_features"] = avoid
                feat = await call({"coordinates": [[req.start.lng, req.start.lat]],
                                   "options": opts, "elevation": True, "instructions": False})
                act = (feat["properties"].get("summary") or {}).get("distance") or 0
                err = abs(act - target) / target if target else 1
                if err < best_err:
                    best_err, best = err, feat
                if err <= _LOOP_TOL or not act:
                    break
                reqlen = max(target * 0.4, min(target * 1.6, reqlen * target / act))
            feat = best

    props = feat["properties"]
    return {
        "coords": feat["geometry"]["coordinates"],   # [lng, lat, ele]
        "distance_m": (props.get("summary") or {}).get("distance"),
        "ascent": props.get("ascent"),
        "loop": loop,
    }
