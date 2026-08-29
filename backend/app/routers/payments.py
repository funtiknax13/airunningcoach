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

    # Сохраняем запись заранее, чтобы получить db_payment.id для return_url
    db_payment = Payment(
        user_id=current_user.id,
        yookassa_id="pending",
        plan=body.plan,
        amount=amount,
        status="pending",
    )
    db.add(db_payment)
    db.flush()  # получаем db_payment.id без commit

    return_url = f"{settings.YOOKASSA_RETURN_URL}?ref={db_payment.id}"
    idempotency_key = str(uuid.uuid4())

    payment = yookassa.Payment.create({
        "amount": {
            "value":    f"{amount}.00",
            "currency": "RUB",
        },
        "confirmation": {
            "type":       "redirect",
            "return_url": return_url,
        },
        "capture":      True,
        "description":  f"AI RunningCoach Premium — {body.plan}",
        "metadata": {
            "user_id": str(current_user.id),
            "plan":    body.plan,
        },
    }, idempotency_key)

    db_payment.yookassa_id = payment.id
    db.commit()

    return {
        "payment_id":        payment.id,
        "confirmation_url":  payment.confirmation.confirmation_url,
    }


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    """ЮКасса отправляет уведомления о смене статуса платежа.

    ЮКасса не подписывает уведомления — тело запроса может прислать кто угодно.
    Поэтому тело используется только чтобы узнать yookassa_id; реальный статус и
    metadata берём напрямую у ЮКассы через API (find_one, авторизовано нашим
    секретным ключом) и активируем Premium только по этим, серверно проверенным,
    данным. Раньше status/metadata брались прямо из тела запроса — подделав его,
    можно было выдать себе Premium без оплаты."""
    body = await request.body()

    try:
        event = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    obj = event.get("object", {})
    yookassa_id = obj.get("id")
    if not yookassa_id:
        return {"status": "ignored"}

    if not _yookassa_configured():
        logger.error("YooKassa webhook received but YooKassa is not configured")
        return {"status": "ignored"}

    import yookassa
    yookassa.Configuration.configure(
        account_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY,
    )
    try:
        yk_payment = yookassa.Payment.find_one(yookassa_id)
    except Exception as e:
        logger.warning("YooKassa webhook: failed to verify payment %s via API: %s", yookassa_id, e)
        raise HTTPException(status_code=502, detail="Verification failed")

    logger.info("YooKassa webhook: id=%s verified_status=%s", yookassa_id, yk_payment.status)

    if yk_payment.status != "succeeded":
        return {"status": "ignored"}

    meta = yk_payment.metadata or {}
    user_id = meta.get("user_id")
    plan = meta.get("plan")

    # Находим платёж
    db_payment = db.query(Payment).filter(Payment.yookassa_id == yookassa_id).first()
    if not db_payment:
        if not user_id or plan not in PLANS:
            logger.warning("YooKassa webhook: verified payment %s has no usable metadata", yookassa_id)
            return {"status": "not_found"}

        # Создаём запись если пропустили (редкий кейс) — amount/plan теперь из
        # проверенного ответа ЮКассы, не из тела вебхука.
        _, amount = PLANS[plan]
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


@router.get("/verify")
async def verify_payment(
    ref: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверяет статус платежа и активирует Premium если оплачено (fallback для вебхука)."""
    db_payment = db.query(Payment).filter(
        Payment.id == ref,
        Payment.user_id == current_user.id,
    ).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if db_payment.status == "succeeded":
        return {"status": "succeeded", "already_active": True}

    if db_payment.status == "cancelled":
        return {"status": "cancelled"}

    # Проверяем статус в ЮКассе
    if not _yookassa_configured():
        return {"status": db_payment.status}

    import yookassa
    yookassa.Configuration.configure(
        account_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY,
    )

    try:
        yk_payment = yookassa.Payment.find_one(db_payment.yookassa_id)
        yk_status = yk_payment.status  # pending | waiting_for_capture | succeeded | cancelled
    except Exception as e:
        logger.warning("YooKassa verify error: %s", e)
        return {"status": db_payment.status}

    if yk_status == "succeeded" and db_payment.status != "succeeded":
        db_payment.status = "succeeded"
        db_payment.paid_at = datetime.now(timezone.utc)

        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            months, _ = PLANS[db_payment.plan]
            now = datetime.now(timezone.utc)
            base = user.premium_until
            if base and base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
            if not base or base < now:
                base = now
            user.is_premium = True
            user.premium_until = base + timedelta(days=months * 30)
            logger.info("Premium activated via verify: user_id=%s until=%s", user.id, user.premium_until)

        db.commit()

    elif yk_status == "cancelled":
        db_payment.status = "cancelled"
        db.commit()

    return {"status": yk_status}


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
