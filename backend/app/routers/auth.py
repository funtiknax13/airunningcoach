# app/routers/auth.py
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    UserCreate, UserLogin, Token, UserResponse,
    UserUpdate, PasswordChange,
    PasswordResetRequest, PasswordResetConfirm,
)
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    generate_verification_token, verification_token_expiry,
)
from app.services.email import send_verification_email, send_password_reset_email
from app.services.rate_limit import get_usage, _is_premium_active
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


# ── Регистрация ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    token, expires = generate_verification_token(), verification_token_expiry()
    trial_until = datetime.now(timezone.utc) + timedelta(days=14)
    db_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        name=user_data.name, age=user_data.age,
        weight=user_data.weight, height=user_data.height,
        is_verified=False,
        verification_token=token, verification_token_expires=expires,
        is_premium=True, premium_until=trial_until,
    )
    db.add(db_user)
    db.commit()

    try:
        await send_verification_email(user_data.email, user_data.name, token, lang=user_data.lang or "ru")
    except Exception as exc:
        logger.error("Verification email failed: %s", exc)

    return {"message": f"Аккаунт создан. Письмо отправлено на {user_data.email}.", "email": user_data.email}


# ── Подтверждение email ───────────────────────────────────────────────────────

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверная или устаревшая ссылка")

    expires = user.verification_token_expires
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Ссылка истекла. Запросите новую.")

    user.is_verified = True
    user.verification_token = user.verification_token_expires = None
    db.commit()
    return RedirectResponse(url="/?verified=1", status_code=302)


class ResendVerificationRequest(BaseModel):
    email: str
    password: Optional[str] = None

@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Если пароль передан — проверяем (защита от отправки на чужой адрес)
    if body.password:
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
    elif not user:
        return {"message": "Если такой email зарегистрирован, письмо будет отправлено."}
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email уже подтверждён")

    user.verification_token = generate_verification_token()
    user.verification_token_expires = verification_token_expiry()
    db.commit()

    try:
        await send_verification_email(user.email, user.name, user.verification_token)
    except Exception as exc:
        logger.error("Resend verification failed: %s", exc)
        raise HTTPException(status_code=500, detail="Не удалось отправить письмо.")

    return {"message": "Письмо отправлено повторно."}


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if user and user.google_id and not user.password_hash:
        raise HTTPException(status_code=400, detail="Этот аккаунт создан через Google. Войдите через Google.")
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email не подтверждён. Проверьте почту.")
    return {"access_token": create_access_token({"sub": str(user.id)}), "token_type": "bearer"}


# ── Профиль ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/limits")
def get_limits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Текущее использование и лимиты AI-запросов."""
    from datetime import timezone
    premium_active = _is_premium_active(current_user, db)
    db.commit()  # сохраняем сброс флага, если он произошёл
    until = current_user.premium_until
    if until and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return {
        "is_premium":    premium_active,
        "premium_until": until.isoformat() if until else None,
        "chat":  get_usage(current_user, "chat", db),
        "plan":  get_usage(current_user, "plan", db),
    }


@router.patch("/me", response_model=UserResponse)
def update_profile(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password")
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Пароль успешно изменён"}


# ── Сброс пароля ──────────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    # Всегда возвращаем одно сообщение — не раскрываем наличие email
    if user and user.is_verified:
        token = generate_verification_token()
        user.reset_token = token
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()
        try:
            await send_password_reset_email(user.email, user.name, token, lang=data.lang or "ru")
        except Exception as exc:
            logger.error("Password reset email failed: %s", exc)

    return {"message": "Если аккаунт с таким email существует, письмо отправлено."}


@router.post("/reset-password")
def reset_password(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверная или устаревшая ссылка")

    expires = user.reset_token_expires
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Ссылка истекла. Запросите новую.")

    user.password_hash = get_password_hash(data.new_password)
    user.reset_token = user.reset_token_expires = None
    db.commit()
    return {"message": "Пароль успешно изменён. Теперь вы можете войти."}


# ── Google OAuth ──────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google")
def google_login():
    """Перенаправляет пользователя на экран согласия Google."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth не настроен")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{settings.APP_BASE_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
    }
    url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """Принимает код от Google, находит/создаёт пользователя, возвращает JWT."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth не настроен")

    # Обмен кода на токен
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{settings.APP_BASE_URL}/auth/google/callback",
            "grant_type": "authorization_code",
        })
    if token_resp.status_code != 200:
        logger.error("Google token exchange failed: %s", token_resp.text)
        return RedirectResponse(url="/?google_error=1", status_code=302)

    access_token = token_resp.json().get("access_token")

    # Получаем информацию о пользователе
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if info_resp.status_code != 200:
        return RedirectResponse(url="/?google_error=1", status_code=302)

    info = info_resp.json()
    google_id = info.get("sub")
    email = info.get("email", "")
    name = info.get("name") or email.split("@")[0]

    if not google_id:
        return RedirectResponse(url="/?google_error=1", status_code=302)

    # Ищем существующего пользователя по google_id или email
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Привязываем google_id к существующему аккаунту
            user.google_id = google_id
            user.is_verified = True
            db.commit()

    if not user:
        # Создаём нового пользователя без пароля
        trial_until = datetime.now(timezone.utc) + timedelta(days=14)
        user = User(
            email=email,
            password_hash="",          # Google-пользователи не входят по паролю
            name=name,
            google_id=google_id,
            is_verified=True,           # Верификация не нужна — Google уже подтвердил
            is_premium=True, premium_until=trial_until,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt = create_access_token({"sub": str(user.id)})
    return RedirectResponse(
        url=f"{settings.APP_BASE_URL}/auth/callback?token={jwt}",
        status_code=302,
    )
