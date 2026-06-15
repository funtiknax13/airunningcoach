# app/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ChatMessage
from app.schemas import AIChatRequest, ChatMessageResponse
from app.dependencies import get_current_user
from app.services.ai_agent import chat_response, build_and_save_plan
from app.services.insights_cache import invalidate_insights_cache
from app.services.rate_limit import check_and_record

_PLAN_TRIGGERS = [
    # RU
    "составь план", "составьте план", "сделай план", "сгенерируй план",
    "создай план", "пересобери план", "обнови план", "перегенерируй план",
    "сделай новый план", "создай новый план", "составить план", "пересоздай план",
    # EN
    "create plan", "generate plan", "make plan", "build plan",
    "new plan", "rebuild plan", "create a plan", "generate a plan", "make a plan",
]

def _is_plan_request(text: str) -> bool:
    lowered = text.lower()
    return any(t in lowered for t in _PLAN_TRIGGERS)

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

    # Если пользователь просит составить/пересобрать план — делаем это в фоне
    plan_requested = _is_plan_request(request.message)
    if plan_requested:
        try:
            check_and_record(current_user, "plan", db)
            await build_and_save_plan(current_user, db)
        except Exception:
            plan_requested = False  # rate limit hit или ошибка — не меняем context_type

    # Сохраняем ответ AI
    context = "plan_generated" if plan_requested else request.context_type
    ai_msg = ChatMessage(
        user_id=current_user.id,
        role="ai",
        content=ai_text,
        context_type=context,
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
