# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from sqlalchemy import text
from app.database import engine, Base
from app.routers import auth, activities, goals, training, chat, ai_insights, payments, support, tools, push
from app.core.config import settings
from app.services.trial_emails import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)

def _migrate():
    """Добавляет новые колонки к существующим таблицам (идемпотентно)."""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS fitness_level VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS running_goal VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_km FLOAT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS training_days INTEGER",
        # server_default TRUE — существующие пользователи не попадают в онбординг
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT TRUE",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            conn.execute(text(sql))
        conn.commit()

_migrate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="AI Running Coach API",
    description="AI-тренер по бегу с персонализированными планами и аналитикой",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLAdmin монтируется ПЕРВЫМ — до любых роутеров и маршрутов
from app.admin import create_admin
create_admin(app)

# API роутеры — все под /api чтобы не конфликтовать с SPA-маршрутами
app.include_router(auth.router,        prefix="/api")
app.include_router(activities.router,  prefix="/api")
app.include_router(goals.router,       prefix="/api")
app.include_router(training.router,    prefix="/api")
app.include_router(chat.router,        prefix="/api")
app.include_router(ai_insights.router, prefix="/api")
app.include_router(payments.router,    prefix="/api")
app.include_router(support.router,     prefix="/api")
app.include_router(tools.router,       prefix="/api")
app.include_router(push.router,        prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Статика фронтенда
CURRENT_FILE = Path(__file__).resolve()
# frontend-v2-dist — сборка Vue (приоритет), fallback на старый vanilla JS
_v2_dist = CURRENT_FILE.parent.parent.parent / "frontend-v2-dist"
_v1_dir  = CURRENT_FILE.parent.parent.parent / "frontend"
FRONTEND_DIR = _v2_dist if _v2_dist.exists() else _v1_dir

# Пути, которые обрабатывает API (с обязательным / после префикса или точное совпадение)
# SPA-маршруты типа /training, /goals и т.д. НЕ начинаются с этих паттернов
API_PREFIXES = (
    "/api/", "/admin/", "/health", "/docs", "/openapi.json",
)

if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    js_dir  = FRONTEND_DIR / "js"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
    img_dir    = FRONTEND_DIR / "images"
    assets_dir = FRONTEND_DIR / "assets"
    if img_dir.exists():
        app.mount("/images", StaticFiles(directory=str(img_dir)), name="images")
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    # Catch-all для SPA: любой GET-запрос, не попадающий в API, отдаёт index.html.
    # Это стандартный способ поддержки history-режима Vue Router / React Router.
    # Важно: этот маршрут должен быть ПОСЛЕДНИМ — после всех API-роутеров.
    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        path = "/" + full_path
        # API и ресурсы — пропускаем (вернётся реальный 404 от роутера)
        if any(path.startswith(p) for p in API_PREFIXES):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Not found"}, status_code=404)

else:
    @app.get("/")
    def root():
        return {"message": "AI Running Coach API", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
