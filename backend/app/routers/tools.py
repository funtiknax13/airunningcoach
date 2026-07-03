# app/routers/tools.py
"""Публичные бесплатные инструменты (лид-магниты) — без авторизации."""
import time

from fastapi import APIRouter, HTTPException, UploadFile, File, Request

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
