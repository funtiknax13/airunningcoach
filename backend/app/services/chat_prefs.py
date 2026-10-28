"""Пожелания к плану из чата: число тренировочных дней, день длинной и свободная
заметка (расписание на неделю, травмы, прочее, для чего нет отдельного поля).

Разбор — не regex, а сама модель в chat_response (см. ai_agent.ChatDecision):
она понимает смысл сообщения надёжнее, чем совпадение по ключевым словам, и
сама решает, что из сказанного стоит запомнить. Код здесь только хранит
то, что модель решила запомнить, и считает срок действия заметки по присланному
ею scope — дата — код, не угадывание модели.

Правило приоритета training_days/long_run_day: пожелание из чата действует,
пока пользователь сам не пересмотрит профиль (сохранение training_days в
профиле сбрасывает его — см. routers/auth.py). Тренер при расхождении советует
обновить профиль (training_days_hint).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PlanPreference

_DEFAULT_NOTE_DAYS = 7   # неизвестный/отсутствующий scope — считаем временным, а не навсегда:
                         # лучше забыть лишнее, чем залипшее правило мешало месяцами


def _note_expiry(scope: Optional[str], days: Optional[int], today: date) -> Optional[date]:
    if scope == "standing":
        return None
    if scope == "this_week":
        return today + timedelta(days=6 - today.weekday())   # до воскресенья этой недели включительно
    if scope == "next_days":
        n = days if days and days > 0 else _DEFAULT_NOTE_DAYS
        return today + timedelta(days=n)
    return today + timedelta(days=_DEFAULT_NOTE_DAYS)


def get_pref(db: Session, user_id: int) -> Optional[PlanPreference]:
    return db.query(PlanPreference).filter(PlanPreference.user_id == user_id).first()


def set_from_chat(
    db: Session, user_id: int, *, training_days: Optional[int] = None,
    long_run_day: Optional[int] = None, note_update: Optional[dict] = None,
    today: Optional[date] = None,
) -> Optional[PlanPreference]:
    """Применяет то, что ChatDecision извлекла из сообщения. Поля со значением
    None — не трогаем (пользователь не менял это сейчас). note_update с пустым
    text — явная просьба "забудь" (модель так и инструктирована). Для обычного
    сообщения без извлечённых пожеланий ничего не пишет в БД (как и раньше)."""
    if training_days is None and long_run_day is None and note_update is None:
        return get_pref(db, user_id)
    today = today or date.today()
    pref = get_pref(db, user_id)
    if pref is None:
        pref = PlanPreference(user_id=user_id)
        db.add(pref)
    if training_days is not None:
        pref.training_days = training_days
    if long_run_day is not None:
        pref.long_run_day = long_run_day
    if note_update is not None:
        text = (note_update.get("text") or "").strip()
        if not text:
            pref.note, pref.note_expires_at = None, None
        else:
            pref.note = text
            expiry = _note_expiry(note_update.get("scope"), note_update.get("days"), today)
            pref.note_expires_at = None if expiry is None else datetime.combine(expiry, time(23, 59, 59))
    db.commit()
    return pref


def active_note(pref: Optional[PlanPreference], today: Optional[date] = None) -> Optional[str]:
    """Текст заметки, если она есть и ещё не просрочена — иначе None (просроченная
    заметка сама перестаёт влиять, без отдельной уборки)."""
    if pref is None or not pref.note:
        return None
    if pref.note_expires_at is not None:
        today = today or date.today()
        if pref.note_expires_at.date() < today:
            return None
    return pref.note


def clear_training_days(db: Session, user_id: int) -> None:
    """Пользователь пересмотрел число дней в профиле — профиль снова источник правды."""
    pref = get_pref(db, user_id)
    if pref is not None and pref.training_days is not None:
        pref.training_days = None


def effective_training_days(user, pref: Optional[PlanPreference]) -> Optional[int]:
    if pref is not None and pref.training_days:
        return pref.training_days
    return getattr(user, "training_days", None)


def effective_long_run_day(pref: Optional[PlanPreference]) -> Optional[int]:
    return pref.long_run_day if pref is not None else None


_DAY_NAMES_RU = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


def _dword(n: int, lang: str) -> str:
    if lang == "en":
        return f"{n} day" + ("" if n == 1 else "s")
    return f"{n} дн."


def training_days_hint(profile_days: Optional[int], requested: int, lang: str = "ru") -> Optional[str]:
    """Текст, который тренер дописывает в конец ответа, если пожелание из чата
    расходится с профилем. None — расхождения нет."""
    if profile_days == requested:
        return None
    if lang == "en":
        base = ("I'll take this into account when building your plans. "
                + (f"Your profile currently says {_dword(profile_days, 'en')} per week"
                   if profile_days else "Your profile doesn't have a number of training days")
                + f" — to keep it from being forgotten, please update it to {requested} "
                  "(Profile → Training).")
    else:
        base = ("Я учту это при составлении планов. "
                + (f"В профиле сейчас указано {_dword(profile_days, 'ru')} в неделю"
                   if profile_days else "В профиле не указано число дней для тренировок")
                + f" — чтобы это не забылось, лучше изменить его на {requested} "
                  "(Профиль → Тренировки).")
    return "\n\n" + base
