# app/routers/support.py
from fastapi import APIRouter, Depends

from app.models import User
from app.schemas import SupportContactRequest
from app.dependencies import get_current_user
from app.services.email import send_support_notification, send_support_autoreply
from app.core.config import settings

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/contact")
async def contact_support(
    data: SupportContactRequest,
    current_user: User = Depends(get_current_user),
):
    # Убираем переводы строк из темы письма — защита от инъекции в email-заголовок
    subject = data.subject.replace("\r", " ").replace("\n", " ").strip()

    await send_support_notification(
        support_email=settings.SUPPORT_EMAIL or settings.GMAIL_USER,
        user_name=current_user.name,
        user_email=current_user.email,
        subject=subject,
        message=data.message,
    )
    await send_support_autoreply(current_user.email, current_user.name, data.lang or "ru")

    return {"message": "sent"}
