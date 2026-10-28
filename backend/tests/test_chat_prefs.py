from datetime import date

from app.models import PlanPreference, User
from app.services import chat_prefs as cp

TODAY = date(2026, 10, 28)   # среда


def _user(db, **kw):
    base = dict(email="a@b.c", password_hash="x", name="T")
    base.update(kw)
    user = User(**base)
    db.add(user)
    db.commit()
    return user


def test_hint_only_when_profile_differs():
    assert cp.training_days_hint(3, 3) is None
    ru = cp.training_days_hint(3, 5)
    assert "3 дн." in ru and "на 5" in ru and "Профиль" in ru and ru.startswith("\n\n")
    assert "не указано" in cp.training_days_hint(None, 5)
    assert "profile" in cp.training_days_hint(3, 5, "en").lower()


def test_set_from_chat_updates_only_given_fields_and_effective_and_reset(db):
    user = User(email="a@b.c", password_hash="x", name="T", training_days=3)
    db.add(user)
    db.commit()

    cp.set_from_chat(db, user.id, training_days=5, long_run_day=5, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert cp.effective_training_days(user, pref) == 5
    assert cp.effective_long_run_day(pref) == 5

    # следующее сообщение не трогает long_run_day (None = "не менялось сейчас")
    cp.set_from_chat(db, user.id, training_days=4, long_run_day=None, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert pref.training_days == 4 and pref.long_run_day == 5

    # профиль пересмотрен -> чат больше не перебивает число дней, день длинной остаётся
    cp.clear_training_days(db, user.id)
    db.commit()
    pref = cp.get_pref(db, user.id)
    assert cp.effective_training_days(user, pref) == 3
    assert cp.effective_long_run_day(pref) == 5


def test_note_standing_never_expires(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "4 дня через 1 день отдыха", "scope": "standing"}, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert pref.note_expires_at is None
    assert cp.active_note(pref, TODAY) == "4 дня через 1 день отдыха"
    assert cp.active_note(pref, date(2027, 1, 1)) == "4 дня через 1 день отдыха"   # навсегда


def test_note_this_week_expires_after_sunday(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "ПТ и СБ свободны", "scope": "this_week"}, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert cp.active_note(pref, TODAY) == "ПТ и СБ свободны"
    assert cp.active_note(pref, date(2026, 11, 1)) == "ПТ и СБ свободны"   # воскресенье той же недели
    assert cp.active_note(pref, date(2026, 11, 2)) is None                 # понедельник следующей — просрочено


def test_note_next_days_expires_after_n_days(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "колено, без интервалов", "scope": "next_days", "days": 3},
                     today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert cp.active_note(pref, date(2026, 10, 31)) == "колено, без интервалов"
    assert cp.active_note(pref, date(2026, 11, 1)) is None


def test_note_unknown_scope_decays_instead_of_sticking_forever(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "что-то странное", "scope": None}, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert cp.active_note(pref, TODAY) == "что-то странное"
    assert cp.active_note(pref, date(2026, 12, 1)) is None   # не навсегда по умолчанию


def test_empty_text_clears_the_note(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "4 дня через день", "scope": "standing"}, today=TODAY)
    cp.set_from_chat(db, user.id, note_update={"text": ""}, today=TODAY)
    pref = cp.get_pref(db, user.id)
    assert pref.note is None and pref.note_expires_at is None


def test_no_note_update_leaves_existing_note_untouched(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, note_update={"text": "4 дня через день", "scope": "standing"}, today=TODAY)
    cp.set_from_chat(db, user.id, training_days=4, note_update=None, today=TODAY)   # обычное сообщение без заметки
    pref = cp.get_pref(db, user.id)
    assert pref.note == "4 дня через день"


def test_set_from_chat_creates_no_row_when_nothing_to_store(db):
    user = _user(db)
    cp.set_from_chat(db, user.id, today=TODAY)   # обычное сообщение, ничего не извлечено
    assert db.query(PlanPreference).count() == 0
