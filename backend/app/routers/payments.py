"""ЮКасса: создание платежа и обработка вебхуков."""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

# Планы: id → (месяцев, сумма в рублях)
PLANS: dict[str, tuple[int, int]] = {
    "month":   (1,  490),
    "quarter": (3, 1323),
    "year":    (12, 4116),
}


class CreatePaymentRequest(BaseModel):
    plan: str  # month | quarter | year


def _yookassa_configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


@router.post("/create")
async def create_payment(
    body: CreatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Неверный тариф")

    if not _yookassa_configured():
        raise HTTPException(status_code=503, detail="Платёжная система не настроена")

    months, amount = PLANS[body.plan]

    import yookassa
    yookassa.Configuration.configure(
        account_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY,
    )

    idempotency_key = str(uuid.uuid4())

    payment = yookassa.Payment.create({
        "amount": {
            "value":    f"{amount}.00",
            "currency": "RUB",
        },
        "confirmation": {
            "type":       "redirect",
            "return_url": settings.YOOKASSA_RETURN_URL,
        },
        "capture":      True,
        "description":  f"AI RunningCoach Premium — {body.plan}",
        "metadata": {
            "user_id": str(current_user.id),
            "plan":    body.plan,
        },
    }, idempotency_key)

    # Сохраняем платёж в БД
    db_payment = Payment(
        user_id=current_user.id,
        yookassa_id=payment.id,
        plan=body.plan,
        amount=amount,
        status="pending",
    )
    db.add(db_payment)
    db.commit()

    return {
        "payment_id":        payment.id,
        "confirmation_url":  payment.confirmation.confirmation_url,
    }


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    """ЮКасса отправляет уведомления о смене статуса платежа."""
    body = await request.body()

    try:
        event = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("event")
    obj = event.get("object", {})
    yookassa_id = obj.get("id")
    status = obj.get("status")

    logger.info("YooKassa webhook: event=%s id=%s status=%s", event_type, yookassa_id, status)

    if event_type != "payment.succeeded" or status != "succeeded":
        return {"status": "ignored"}

    # Находим платёж
    db_payment = db.query(Payment).filter(Payment.yookassa_id == yookassa_id).first()
    if not db_payment:
        # Пробуем получить данные из метаданных вебхука
        meta = obj.get("metadata", {})
        user_id = meta.get("user_id")
        plan = meta.get("plan")
        if not user_id or not plan:
            logger.warning("YooKassa webhook: payment %s not found in DB", yookassa_id)
            return {"status": "not_found"}

        # Создаём запись если пропустили (редкий кейс)
        _, amount = PLANS.get(plan, (1, 0))
        db_payment = Payment(
            user_id=int(user_id),
            yookassa_id=yookassa_id,
            plan=plan,
            amount=amount,
            status="pending",
        )
        db.add(db_payment)

    if db_payment.status == "succeeded":
        return {"status": "already_processed"}

    # Обновляем статус платежа
    db_payment.status = "succeeded"
    db_payment.paid_at = datetime.now(timezone.utc)

    # Активируем Premium
    user = db.query(User).filter(User.id == db_payment.user_id).first()
    if user:
        months, _ = PLANS[db_payment.plan]
        now = datetime.now(timezone.utc)

        # Продлеваем от текущей даты окончания, если Premium ещё активен
        base = user.premium_until
        if base and base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        if not base or base < now:
            base = now

        user.is_premium = True
        user.premium_until = base + timedelta(days=months * 30)
        logger.info(
            "Premium activated: user_id=%s plan=%s until=%s",
            user.id, db_payment.plan, user.premium_until,
        )

    db.commit()
    return {"status": "ok"}


@router.get("/history")
def payment_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id":         p.yookassa_id,
            "plan":       p.plan,
            "amount":     p.amount,
            "status":     p.status,
            "created_at": p.created_at,
            "paid_at":    p.paid_at,
        }
        for p in payments
    ]
