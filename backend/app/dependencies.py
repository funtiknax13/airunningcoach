# app/dependencies.py
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import decode_token
from app.models import User

security = HTTPBearer()

# Не пишем last_active_at на каждый запрос (их много на сессию) — обновляем не
# чаще раза в этот интервал, для DAU/WAU/MAU точности более чем достаточно.
_LAST_ACTIVE_UPDATE_INTERVAL = timedelta(minutes=5)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    now = datetime.now(timezone.utc)
    last_active = user.last_active_at
    if last_active is not None and last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)
    if last_active is None or now - last_active > _LAST_ACTIVE_UPDATE_INTERVAL:
        user.last_active_at = now
        db.commit()

    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Только для админ-инструментов (Admin Tools). Не админ → 403."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user