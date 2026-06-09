# app/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ChatMessage
from app.schemas import AIChatRequest, ChatMessageResponse
from app.dependencies import get_current_user
from app.services.ai_agent import chat_response
from app.services.insights_cache import invalidate_insights_cache
from app.services.rate_limit import check_and_record

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def chat_with_ai(
    request: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем rate limit
    check_and_record(current_user, "chat", db)

    # Сохраняем сообщение пользователя
    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=request.message,
        context_type=request.context_type,
    )
    db.add(user_msg)
    db.flush()

    # Загружаем историю для контекста (последние 20 сообщений)
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()[::-1]
    )

    # Получаем ответ агента
    ai_text = await chat_response(request.message, current_user, db, history, lang=request.lang or "ru")

    # Сохраняем ответ AI
    ai_msg = ChatMessage(
        user_id=current_user.id,
        role="ai",
        content=ai_text,
        context_type=request.context_type,
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    # Разговор с тренером мог изменить контекст — сбрасываем кеш инсайтов
    invalidate_insights_cache(current_user.id, db)

    return ai_msg


@router.get("/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.id.asc())
        .limit(limit)
        .all()
    )
    return messages
