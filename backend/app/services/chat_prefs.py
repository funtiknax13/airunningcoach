"""Пожелания к плану из чата: число тренировочных дней и день длинной пробежки.

Разбор — детерминированный (регулярные выражения), без вызова ИИ: дёшево,
предсказуемо и проверяемо тестами. Осознанно консервативный: пропускает вопросы,
отрицания и фразы без намерения («хочу/буду/давай...»), чтобы не записать в
пожелания то, что пользователь не просил. Всё, что не распознано, остаётся в
свободном тексте чата (см. ai_agent._plan_chat_prefs) — как и раньше.

Правило приоритета: пожелание из чата действует, пока пользователь сам не
пересмотрит профиль (сохранение training_days в профиле сбрасывает его — см.
routers/auth.py). Тренер при расхождении советует обновить профиль (training_days_hint).
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PlanPreference

_NUM_WORDS = {
    "один": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7,
}
_NUM = r"(\d|" + "|".join(_NUM_WORDS) + r")"
_FREQ_RU = re.compile(
    _NUM + r"\s*(?:раза?|дня|дней|день|тренировк\w*|пробежк\w*)\s*(?:в|за)\s*недел", re.I)
_FREQ_EN = re.compile(r"(\d)\s*(?:times|days|runs|workouts|sessions)\s*(?:a|per|each)\s*week", re.I)

_DAYS = {
    "понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4,
    "суббот": 5, "воскресен": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
}
_LONG_RU = re.compile(
    r"длинн\w*\s+(?:пробежк\w*\s+|тренировк\w*\s+|бег\w*\s+)?(?:в|на)\s+(понедельник|вторник|сред\w*|четверг|пятниц\w*|суббот\w*|воскресен\w*)",
    re.I)
_LONG_EN = re.compile(r"long\s+(?:run\s+)?on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", re.I)

_INTENT = ("хочу", "хотел", "хотела", "буду", "планирую", "готов", "могу", "давай", "сделай",
           "составь", "предпочит", "лучше", "нужно", "надо", "want", "would like", "prefer",
           "can ", "let's", "i'll", "i will")
_NEGATION = re.compile(r"\b(не|нет|нельзя|never|not|don't|dont|can't|cannot)\b", re.I)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?\n])\s+", text.strip())
    return [p for p in parts if p]


def _day_index(word: str) -> Optional[int]:
    w = word.lower()
    for stem, idx in _DAYS.items():
        if w.startswith(stem):
            return idx
    return None


def _negated(sentence: str, match_start: int) -> bool:
    return bool(_NEGATION.search(sentence[max(0, match_start - 30):match_start]))


def extract_prefs(text: str) -> dict:
    """{'training_days': int?, 'long_run_day': int?} — только то, что удалось надёжно распознать."""
    out: dict = {}
    for sent in _sentences(text or ""):
        low = sent.lower()
        if sent.rstrip().endswith("?"):
            continue                                   # вопрос, а не пожелание
        has_intent = any(w in low for w in _INTENT)

        for pat in (_FREQ_RU, _FREQ_EN):
            m = pat.search(sent)
            if m and has_intent and not _negated(sent, m.start()):
                raw = m.group(1).lower()
                n = int(raw) if raw.isdigit() else _NUM_WORDS.get(raw)
                if n and 1 <= n <= 7:
                    out["training_days"] = n
                break

        for pat in (_LONG_RU, _LONG_EN):
            m = pat.search(sent)
            if m and not _negated(sent, m.start()):
                idx = _day_index(m.group(1))
                if idx is not None:
                    out["long_run_day"] = idx
                break
    return out


# ── хранение и эффективные значения ────────────────────────────────────────

def get_pref(db: Session, user_id: int) -> Optional[PlanPreference]:
    return db.query(PlanPreference).filter(PlanPreference.user_id == user_id).first()


def apply_chat_message(db: Session, user_id: int, text: str) -> dict:
    """Разбирает сообщение пользователя и сохраняет найденное. Возвращает найденное."""
    found = extract_prefs(text)
    if not found:
        return {}
    pref = get_pref(db, user_id)
    if pref is None:
        pref = PlanPreference(user_id=user_id)
        db.add(pref)
    if "training_days" in found:
        pref.training_days = found["training_days"]
    if "long_run_day" in found:
        pref.long_run_day = found["long_run_day"]
    db.commit()
    return found


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
