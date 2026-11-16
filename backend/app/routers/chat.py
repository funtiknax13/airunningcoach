# app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ChatMessage, ApiUsage
from app.schemas import AIChatRequest, ChatMessageResponse, ConfirmPlanDraftRequest
from app.dependencies import get_current_user
from datetime import datetime, timedelta, timezone

from app.services import coach_agent
from app.services.ai_agent import confirm_plan_draft
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
    chat_usage_id = check_and_record(current_user, "chat", db)

    # Сохраняем сообщение пользователя. commit (не flush) — дальше идёт await
    # к DeepSeek, во время которого coach_agent.respond() освобождает соединение
    # обратно в пул; flush без commit откатился бы вместе с закрытием сессии.
    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=request.message,
        context_type=request.context_type,
    )
    db.add(user_msg)
    db.commit()

    # Загружаем историю для контекста (последние 20 сообщений)
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()[::-1]
    )

    result = await coach_agent.respond(current_user, db, history, request.lang or "ru")
    if result.unavailable:
        # Refund THIS turn, not another concurrent request's last usage.
        db.query(ApiUsage).filter(ApiUsage.id == chat_usage_id,
                                 ApiUsage.user_id == current_user.id).delete()
        db.commit()
        return ChatMessage(id=0, user_id=current_user.id, role="ai", content=result.reply,
                           context_type="general", created_at=datetime.now(timezone.utc))
    try:
        coach_agent.persist_proposal(result, current_user, db)
    except HTTPException as exc:
        db.rollback()
        # Surface quota/stale-state failures; discard the model's premature promise.
        detail = exc.detail
        result = coach_agent.Result(detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail))
    ai_msg = ChatMessage(user_id=current_user.id, role="ai", content=result.reply,
        context_type="plan_proposal" if result.draft else "general", plan_draft=result.draft)
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    invalidate_insights_cache(current_user.id, db)
    return ai_msg


@router.post("/plans/confirm", response_model=ChatMessageResponse)
def confirm_plan_proposal(
    body: ConfirmPlanDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Применяет черновик, предложенный сообщением message_id (кнопка «Да, пересобери
    план» под сообщением тренера). Сохраняет РОВНО тот черновик — не генерирует план
    заново, иначе превью, которое уже увидел пользователь, могло бы разойтись с
    итогом. Бесплатно (квота "plan" уже списана при подготовке черновика)."""
    # Serialize confirmations and proposal publication for the same user.
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == body.message_id, ChatMessage.user_id == current_user.id)
        .first()
    )
    if not msg or msg.context_type != "plan_proposal" or not msg.plan_draft:
        raise HTTPException(status_code=404, detail="Предложение плана не найдено")

    if msg.plan_draft.get("agent_version") == 1:
        coach_agent.confirm(msg.plan_draft, current_user, db)
    else:
        draft_start = datetime.fromisoformat(msg.plan_draft["start"])
        if draft_start.date() < (datetime.now(timezone.utc) - timedelta(days=1)).date():
            raise HTTPException(status_code=409, detail="Предложение устарело, попроси тренера пересобрать план ещё раз")
        confirm_plan_draft(current_user, db, msg.plan_draft)
    msg.context_type = "plan_proposal_confirmed"   # кнопка больше не показывается при перезагрузке чата

    done_text = ("Done — the plan is saved, check the Training tab." if body.lang == "en"
                 else "Готово — план сохранён, можешь посмотреть его на вкладке «План».")
    done_msg = ChatMessage(user_id=current_user.id, role="ai", content=done_text, context_type="plan_generated")
    db.add(done_msg)
    db.commit()
    db.refresh(done_msg)
    invalidate_insights_cache(current_user.id, db)
    return done_msg


@router.get("/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сколько фоновых AI-сообщений (авторазбор тренировки/плана) ещё не просмотрено.

    Считается по факту наличия сообщения в БД, а не по клиентскому флагу —
    иначе если открыть чат раньше, чем фоновый анализ успел записать сообщение,
    бейдж гаснет, а сообщение так и не показывается (баг, который это чинит)."""
    count = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id, ChatMessage.role == "ai", ChatMessage.read == False)
        .count()
    )
    return {"count": count}


@router.post("/mark-read")
def mark_chat_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id, ChatMessage.role == "ai", ChatMessage.read == False,
    ).update({"read": True})
    db.commit()
    return {"count": 0}
