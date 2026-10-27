# app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ChatMessage
from app.schemas import AIChatRequest, ChatMessageResponse, ConfirmPlanDraftRequest
from app.dependencies import get_current_user
from datetime import datetime, timedelta, timezone

from app.services import chat_prefs
from app.services.ai_agent import chat_response, prepare_plan_draft, confirm_plan_draft, _UNAVAILABLE_MSG
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

    # Если пользователь просит составить/пересобрать план — готовим черновик ДО
    # генерации ответа (чтобы сам ответ мог опираться на то, что реально получилось),
    # но НЕ сохраняем его сразу: пользователь должен подтвердить кнопкой под
    # сообщением тренера (POST /chat/plans/confirm) — см. docstring prepare_plan_draft.
    # Квота "plan" списывается здесь (черновик — это и есть обращение к ИИ), а не
    # при подтверждении: подтверждение само по себе ничего не генерирует.
    draft = None
    plan_requested = _is_plan_request(request.message)
    if plan_requested:
        try:
            check_and_record(current_user, "plan", db)
            draft = await prepare_plan_draft(current_user, db)
            if draft["source"] != "ai":
                refund_last_usage(db, current_user.id, "plan")   # ИИ не тратился — попытка не сгорает
        except Exception:
            plan_requested = False  # rate limit hit или ошибка — не меняем context_type
            draft = None

    # Получаем ответ агента
    ai_text = await chat_response(
        request.message, current_user, db, history,
        lang=request.lang or "ru",
        plan_draft_summary=draft["summary"] if draft else None,
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

    # Сохраняем ответ AI. Черновик плана (если есть) едет вместе с сообщением —
    # фронт рисует под ним превью и кнопку подтверждения (POST /chat/plans/confirm).
    context = "plan_proposal" if draft else request.context_type
    ai_msg = ChatMessage(
        user_id=current_user.id,
        role="ai",
        content=ai_text,
        context_type=context,
        plan_draft=draft,
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    # Разговор с тренером мог изменить контекст — сбрасываем кеш инсайтов
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
    msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == body.message_id, ChatMessage.user_id == current_user.id)
        .first()
    )
    if not msg or msg.context_type != "plan_proposal" or not msg.plan_draft:
        raise HTTPException(status_code=404, detail="Предложение плана не найдено")

    draft_start = datetime.fromisoformat(msg.plan_draft["start"])
    if draft_start.date() < (datetime.now(timezone.utc) - timedelta(days=1)).date():
        raise HTTPException(status_code=409, detail="Предложение устарело, попроси тренера пересобрать план ещё раз")

    confirm_plan_draft(current_user, db, msg.plan_draft)
    msg.context_type = "plan_proposal_confirmed"   # кнопка больше не показывается при перезагрузке чата

    done_text = ("Done — the plan is saved, check the Training tab." if body.lang == "en"
                 else "Готово — план сохранён, можешь посмотреть его на вкладке «Тренировки».")
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
