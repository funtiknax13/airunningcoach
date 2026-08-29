from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional

_DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./running_coach.db"
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 дней (10 дней = 14400)

    # Gmail SMTP
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "AIRunningCoach"

    # ALTCHA captcha — секрет для подписи челленджей (пусто = капча выключена, для dev)
    ALTCHA_HMAC_KEY: str = ""

    # OpenRouteService — генератор маршрутов (публичный инструмент). Ключ на сервере,
    # клиент ходит через /api/tools/route (иначе ключ утёк бы в браузер).
    ORS_API_KEY: str = ""

    # App base URL for verification links
    APP_BASE_URL: str = "http://localhost:8000"

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "mailto:running.coach.mail@gmail.com"

    # AI-провайдеры: Groq — основной, DeepSeek — на подхвате (failover при 429/сбое).
    # Оба OpenAI-совместимые. Провайдер «включён», если задан его ключ.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    # Прокси ТОЛЬКО для Groq (сервер в РФ → гео-блок Groq). Пусто = напрямую.
    # Форматы: http://user:pass@host:port или socks5://host:port (нужен httpx[socks]).
    GROQ_PROXY: str = ""

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ЮКасса
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "https://airunningcoach.pro/payment/success"

    # Ignored legacy keys
    GEMINI_API_KEY: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_must_be_overridden(cls, v: str) -> str:
        # Дефолт публичный (в гите) — если он дошёл до прода, любой может подделать
        # JWT на любого user_id, включая админов. Падаем при старте, а не молча
        # работаем с небезопасным ключом.
        if v == _DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY не задан — используется публичный дефолт из репозитория. "
                "Задайте реальный секрет в .env (SECRET_KEY=...) перед запуском."
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()