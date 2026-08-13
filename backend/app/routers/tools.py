# app/routers/tools.py
"""Публичные бесплатные инструменты (лид-магниты) — без авторизации."""
import time

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.services.gpx_parser import parse_gpx
from app.services.fit_parser import parse_fit

router = APIRouter(prefix="/tools", tags=["tools"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ — с запасом для трека в несколько часов
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
        raise HTTPException(status_code=413, detail="Файл слишком большой (максимум 5 МБ)")

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
    }


# ── Генератор маршрутов (OpenRouteService через серверный ключ) ─────────────────
ORS_URL = "https://api.openrouteservice.org/v2/directions/"
ORS_MAX_M = 100000          # потолок длины маршрута у бесплатного ORS (100 км)
_LOOP_TOL = 0.05            # целимся в ±5% по длине кольца
_LOOP_TRIES = 5            # попыток коррекции длины
_LOOP_POINTS = 4


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
            body = {"coordinates": [[req.start.lng, req.start.lat], [req.finish.lng, req.finish.lat]],
                    "elevation": True, "instructions": False}
            if avoid:
                body["options"] = {"avoid_features": avoid}
            feat = await call(body)
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
