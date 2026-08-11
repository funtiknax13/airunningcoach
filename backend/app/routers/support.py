# app/routers/support.py
"""Сторона пользователя (обращающегося): создать обращение, список своих тредов,
тред целиком, ответить. Тикет-система — заменяет прежнюю поддержку через почту.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SupportTicket
from app.schemas import (
    SupportTicketSummary, SupportTicketDetail,
    SupportCreateRequest, SupportReplyRequest,
)
from app.dependencies import get_current_user
from app.services import support as svc

router = APIRouter(prefix="/support", tags=["support"])


def _detail(ticket: SupportTicket) -> SupportTicketDetail:
    return SupportTicketDetail(
        id=ticket.id, status=ticket.status, created_at=ticket.created_at,
        messages=ticket.messages,  # отсортированы по id (relationship order_by)
    )


def _get_owned_ticket(db: Session, ticket_id: int, user: User) -> SupportTicket:
    """Тред должен принадлежать текущему пользователю. Чужой/несуществующий → 404
    (именно 404, а не 403 — чтобы не палить существование чужих id)."""
    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id, SupportTicket.created_by_user_id == user.id)
        .first()
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    return ticket


@router.post("/tickets", response_model=SupportTicketSummary)
def create_ticket(
    payload: SupportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = svc.create_ticket(db, current_user, payload.body.strip())
    db.commit()
    db.refresh(ticket)
    return SupportTicketSummary(
        id=ticket.id, status=ticket.status, created_at=ticket.created_at,
        preview=svc.ticket_preview(ticket), has_unread=False,
    )


@router.get("/tickets", response_model=List[SupportTicketSummary])
def my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.created_by_user_id == current_user.id)
        .order_by(SupportTicket.id.desc())
        .all()
    )
    return [
        SupportTicketSummary(
            id=t.id, status=t.status, created_at=t.created_at,
            preview=svc.ticket_preview(t), has_unread=svc.has_unread_staff_reply(t),
        )
        for t in tickets
    ]


# ВАЖНО: этот маршрут объявлен ДО /tickets/{ticket_id}, иначе "unread-count"
# попал бы в {ticket_id} и упал бы на приведении к int.
@router.get("/tickets/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"count": svc.unread_count_for_user(db, current_user)}


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_owned_ticket(db, ticket_id, current_user)
    svc.mark_read_by_reporter(db, ticket)  # просмотр треда гасит бейдж
    db.commit()
    db.refresh(ticket)
    return _detail(ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=SupportTicketDetail)
def add_message(
    ticket_id: int,
    payload: SupportReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_owned_ticket(db, ticket_id, current_user)
    # Закрытый тикет не переоткрывается ответом пользователя — новый вопрос = новый тикет.
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="Обращение закрыто. Создайте новое обращение.")
    svc.add_message(db, ticket, sender=current_user, is_staff=False, body=payload.body.strip())
    db.commit()
    db.refresh(ticket)
    return _detail(ticket)
