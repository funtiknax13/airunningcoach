# app/services/support.py
"""Логика поддержки (тикеты). Синхронный слой над SQLAlchemy Session.

Ключевые правила (не размывать):
1. Общий инбокс — «прочитано» помечается один раз для всей команды (read_at на
   сообщении), а не персонально по агенту.
2. Закрытый тикет не переоткрывается ответом пользователя — это проверяет роутер
   (409). Переоткрыть может только сотрудник (сменой статуса).
3. «Ждёт ответа» (последнее слово за пользователем) — отдельное состояние от
   «есть непрочитанное»; вычисляется на стороне staff-списка.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import SupportTicket, SupportMessage, User

MAX_BODY = 5000


def create_ticket(db: Session, user: User, body: str) -> SupportTicket:
    """Новое обращение = тикет open + первое сообщение пользователя. Не коммитит."""
    ticket = SupportTicket(status="open", created_by_user_id=user.id)
    db.add(ticket)
    db.flush()  # нужен ticket.id для сообщения
    db.add(SupportMessage(
        ticket_id=ticket.id, sender_user_id=user.id, is_staff=False, body=body,
    ))
    db.flush()
    return ticket


def add_message(db: Session, ticket: SupportTicket, sender: User | None, is_staff: bool, body: str) -> SupportMessage:
    """Дописать реплику в тред. Закрытый тикет здесь НЕ переоткрывается — это
    ответственность вызывающего (пользователю ответ в закрытый блокируется 409;
    сотрудник переоткрывает явной сменой статуса). Не коммитит."""
    msg = SupportMessage(
        ticket_id=ticket.id,
        sender_user_id=sender.id if sender else None,
        is_staff=is_staff, body=body,
    )
    db.add(msg)
    db.flush()
    return msg


def mark_read_by_staff(db: Session, ticket: SupportTicket) -> None:
    """Сотрудник открыл тред → все сообщения пользователя помечаются прочитанными."""
    db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket.id,
        SupportMessage.is_staff == False,  # noqa: E712
        SupportMessage.read_at.is_(None),
    ).update({"read_at": datetime.now(timezone.utc)}, synchronize_session=False)


def mark_read_by_reporter(db: Session, ticket: SupportTicket) -> None:
    """Пользователь открыл свой тред → сообщения сотрудников помечаются прочитанными."""
    db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket.id,
        SupportMessage.is_staff == True,  # noqa: E712
        SupportMessage.read_at.is_(None),
    ).update({"read_at": datetime.now(timezone.utc)}, synchronize_session=False)


def unread_count_for_user(db: Session, user: User) -> int:
    """Сколько СВОИХ тикетов пользователя имеют непрочитанный ответ сотрудника — бейдж в шапке."""
    return (
        db.query(SupportTicket.id)
        .join(SupportMessage, SupportMessage.ticket_id == SupportTicket.id)
        .filter(
            SupportTicket.created_by_user_id == user.id,
            SupportMessage.is_staff == True,  # noqa: E712
            SupportMessage.read_at.is_(None),
        )
        .distinct()
        .count()
    )


def unread_count_for_staff(db: Session) -> int:
    """Сколько тикетов имеют непрочитанное сообщение от пользователей — бейдж в админке.
    Общий для всей команды."""
    return (
        db.query(SupportTicket.id)
        .join(SupportMessage, SupportMessage.ticket_id == SupportTicket.id)
        .filter(
            SupportMessage.is_staff == False,  # noqa: E712
            SupportMessage.read_at.is_(None),
        )
        .distinct()
        .count()
    )


def ticket_preview(ticket: SupportTicket, length: int = 120) -> str:
    """Первые N символов первого сообщения — превью в списках."""
    first = ticket.messages[0] if ticket.messages else None
    return (first.body[:length] if first else "").strip()


def has_unread_staff_reply(ticket: SupportTicket) -> bool:
    """Есть ли в треде непрочитанный пользователем ответ сотрудника (для has_unread)."""
    return any(m.is_staff and m.read_at is None for m in ticket.messages)
