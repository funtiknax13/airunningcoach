# app/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ChatMessage
from app.schemas import AIChatRequest, ChatMessageResponse
from app.dependencies import get_current_user
from datetime import datetime, timezone

from app.services import chat_prefs
from app.services.ai_agent import chat_response, build_and_save_plan, _UNAVAILABLE_MSG
from app.services.insights_cache import invalidate_insights_cache
from app.services.rate_limit import check_and_record, refund_last_usage

_PLAN_TRIGGERS_EN = [
    "create plan", "generate plan", "make plan", "build plan",
    "new plan", "rebuild plan", "create a plan", "generate a plan", "make a plan",
    "update plan", "update the plan", "change plan", "change the plan", "adjust plan",
]

# Стемы охватывают разные формы одного глагола (обнови/обновить/обновим/обновляй —
# всё содержит "обнов"). Раньше проверялись только точные фразы вроде "обнови план" —
# реальные пользователи просят иначе ("убери ходьбу из плана", "поменяй план",
# "можешь изменить план"), и такие просьбы не запускали настоящую пересборку, хотя
# модель (по своему собственному, более гибкому пониманию текста) всё равно уверяла,
# что план обновлён — см. docstring chat_response().
_PLAN_VERB_STEMS = [
    "обнов", "пересобер", "пересобир", "пересоздан", "пересоздай", "перегенерир",
    "созда", "состав", "сформир", "сгенерир", "поменя", "измен",
    "скорректир", "подправ", "перепиш", "перестро", "убр", "убер", "убир", "верн", "замен",
    "пересмотр", "добав",
]
_PLAN_ANCHOR_NOUNS = ["план", "трениров"]

def _is_plan_request(text: str) -> bool:
    lowered = text.lower()
    if any(t in lowered for t in _PLAN_TRIGGERS_EN):
        return True
    has_anchor = any(n in lowered for n in _PLAN_ANCHOR_NOUNS)
    has_verb = any(v in lowered for v in _PLAN_VERB_STEMS)
    return has_anchor and has_verb

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def chat_with_ai(
    request: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем rate limit
    check_and_record(current_user, "chat", db)

    # Сохраняем сообщение пользователя. commit (не flush) — дальше идёт await
    # к DeepSeek, во время которого chat_response() освобождает это соединение
    # обратно в пул; flush без commit откатился бы вместе с закрытием сессии.
    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=request.message,
        context_type=request.context_type,
    )
    db.add(user_msg)
    db.commit()

    # Пожелания к плану из этого сообщения («хочу 5 раз в неделю», «длинную в воскресенье»).
    # Действуют до пересмотра профиля пользователем; при расхождении с профилем тренер
    # допишет совет обновить профиль (см. ниже).
    wishes = chat_prefs.apply_chat_message(db, current_user.id, request.message)
    profile_days = current_user.training_days

    # Загружаем историю для контекста (последние 20 сообщений)
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
        .all()[::-1]
    )

    # Если пользователь просит составить/пересобрать план — делаем это ДО генерации
    # ответа, чтобы сам ответ мог опираться на то, что реально произошло, а не
    # утверждать "план обновлён" вслепую (см. docstring chat_response).
    plan_requested = _is_plan_request(request.message)
    if plan_requested:
        try:
            check_and_record(current_user, "plan", db)
            outcome = await build_and_save_plan(current_user, db)
            if outcome.source != "ai":
                refund_last_usage(db, current_user.id, "plan")   # ИИ не тратился — попытка не сгорает
        except Exception:
            plan_requested = False  # rate limit hit или ошибка — не меняем context_type

    # Получаем ответ агента
    ai_text = await chat_response(
        request.message, current_user, db, history,
        lang=request.lang or "ru", plan_just_regenerated=plan_requested,
    )

    # Подсказка про профиль не зависит от ИИ: пожелание уже сохранено кодом.
    hint = None
    if wishes.get("training_days"):
        hint = chat_prefs.training_days_hint(profile_days, wishes["training_days"], request.lang or "ru")

    if ai_text == _UNAVAILABLE_MSG:
        # Сбой ИИ — не сохраняем это в историю как «совет тренера» и не списываем попытку.
        refund_last_usage(db, current_user.id, "chat")
        return ChatMessage(id=0, user_id=current_user.id, role="ai", content=ai_text + (hint or ""),
                           context_type=request.context_type, created_at=datetime.now(timezone.utc))

    if hint:
        ai_text += hint

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
