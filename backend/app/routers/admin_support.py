# app/routers/admin_support.py
"""Сторона сотрудника (Admin Tools): список тикетов с фильтром/пагинацией,
тред, ответ, переключение статуса, счётчики бейджей. Доступ — только is_admin.

Уведомления пользователю — только в приложении (бейдж), писем не шлём.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import User, SupportTicket
from app.schemas import (
    AdminSupportRow, AdminSupportList, SupportTicketDetail,
    SupportReplyRequest, SupportBadgeCounts,
)
from app.dependencies import get_current_admin
from app.services import support as svc

router = APIRouter(prefix="/admin/support", tags=["admin-support"])

PAGE_SIZE = 25


def _row(t: SupportTicket) -> AdminSupportRow:
    last = t.messages[-1] if t.messages else None
    return AdminSupportRow(
        id=t.id, status=t.status, created_at=t.created_at,
        user_name=t.created_by.name if t.created_by else None,
        user_email=t.created_by.email if t.created_by else None,
        preview=svc.ticket_preview(t),
        last_at=last.created_at if last else None,
        unread=any(not m.is_staff and m.read_at is None for m in t.messages),
        # последнее слово за пользователем (staff мог прочитать, но не ответил)
        awaiting_reply=bool(t.messages) and not t.messages[-1].is_staff,
        can_reply=t.created_by_user_id is not None,
    )


@router.get("", response_model=AdminSupportList)
def list_tickets(
    status: str = Query("all"),   # all | open | closed
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    base = db.query(SupportTicket)
    if status == "open":
        base = base.filter(SupportTicket.status == "open")
    elif status == "closed":
        base = base.filter(SupportTicket.status == "closed")

    total = base.count()
    tickets = (
        base.options(
            selectinload(SupportTicket.messages),
            selectinload(SupportTicket.created_by),
        )
        # "open" > "closed" по алфавиту → desc кладёт открытые сверху
        .order_by(SupportTicket.status.desc(), SupportTicket.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return AdminSupportList(
        tickets=[_row(t) for t in tickets],
        total=total, page=page, page_size=PAGE_SIZE,
    )


# Объявлен ДО /{ticket_id}, иначе "badge-counts" попал бы в {ticket_id}.
@router.get("/badge-counts", response_model=SupportBadgeCounts)
def badge_counts(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    return SupportBadgeCounts(tickets=svc.unread_count_for_staff(db))


def _get_ticket(db: Session, ticket_id: int) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    return ticket


@router.get("/{ticket_id}", response_model=SupportTicketDetail)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    ticket = _get_ticket(db, ticket_id)
    svc.mark_read_by_staff(db, ticket)  # открытие треда гасит staff-бейдж
    db.commit()
    db.refresh(ticket)
    return SupportTicketDetail(
        id=ticket.id, status=ticket.status, created_at=ticket.created_at,
        messages=ticket.messages,
    )


@router.post("/{ticket_id}/reply", response_model=SupportTicketDetail)
def reply(
    ticket_id: int,
    payload: SupportReplyRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ticket = _get_ticket(db, ticket_id)
    if ticket.created_by_user_id is None:
        raise HTTPException(status_code=409, detail="У обращения нет аккаунта-получателя")
    svc.add_message(db, ticket, sender=admin, is_staff=True, body=payload.body.strip())
    db.commit()
    db.refresh(ticket)
    return SupportTicketDetail(
        id=ticket.id, status=ticket.status, created_at=ticket.created_at,
        messages=ticket.messages,
    )


@router.post("/{ticket_id}/status", response_model=SupportTicketDetail)
def toggle_status(
    ticket_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    ticket = _get_ticket(db, ticket_id)
    ticket.status = "closed" if ticket.status == "open" else "open"
    db.commit()
    db.refresh(ticket)
    return SupportTicketDetail(
        id=ticket.id, status=ticket.status, created_at=ticket.created_at,
        messages=ticket.messages,
    )
