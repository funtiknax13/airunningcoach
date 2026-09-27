import pytest

from app.models import PlanPreference, User
from app.services import chat_prefs as cp
from tests.conftest import make_user


@pytest.mark.parametrize("text,expected", [
    ("Хочу тренироваться 5 раз в неделю", {"training_days": 5}),
    ("хочу бегать пять раз в неделю", {"training_days": 5}),
    ("Давай 3 дня в неделю, остальное отдых", {"training_days": 3}),
    ("Планирую 4 тренировки в неделю.", {"training_days": 4}),
    ("I want 4 days a week", {"training_days": 4}),
    ("Хочу длинную пробежку в воскресенье", {"long_run_day": 6}),
    ("хочу длинную в субботу и 4 раза в неделю", {"training_days": 4, "long_run_day": 5}),
    ("long run on Saturday please, I want 3 times a week", {"training_days": 3, "long_run_day": 5}),
])
def test_extracts_wishes(text, expected):
    assert cp.extract_prefs(text) == expected


@pytest.mark.parametrize("text", [
    "Можно ли 5 раз в неделю?",                      # вопрос
    "Не хочу 5 раз в неделю",                         # отрицание
    "Я не смогу бегать 4 раза в неделю",
    "Обычно бегаю 3 раза в неделю",                   # нет намерения
    "Сегодня бегал 5 км",
    "Не хочу длинную в воскресенье",
    "",
])
def test_ignores_questions_negations_and_facts(text):
    assert cp.extract_prefs(text) == {}


def test_out_of_range_ignored():
    assert cp.extract_prefs("Хочу 9 раз в неделю") == {}


def test_hint_only_when_profile_differs():
    assert cp.training_days_hint(3, 3) is None
    ru = cp.training_days_hint(3, 5)
    assert "3 дн." in ru and "на 5" in ru and "Профиль" in ru and ru.startswith("\n\n")
    assert "не указано" in cp.training_days_hint(None, 5)
    assert "profile" in cp.training_days_hint(3, 5, "en").lower()


def test_apply_and_effective_and_reset(db):
    user = User(email="a@b.c", password_hash="x", name="T", training_days=3)
    db.add(user)
    db.commit()
    assert cp.apply_chat_message(db, user.id, "Хочу 5 раз в неделю, длинную в субботу") == {
        "training_days": 5, "long_run_day": 5}
    pref = cp.get_pref(db, user.id)
    assert cp.effective_training_days(user, pref) == 5
    assert cp.effective_long_run_day(pref) == 5
    # профиль пересмотрен -> чат больше не перебивает число дней, день длинной остаётся
    cp.clear_training_days(db, user.id)
    db.commit()
    pref = cp.get_pref(db, user.id)
    assert cp.effective_training_days(user, pref) == 3
    assert cp.effective_long_run_day(pref) == 5


def test_apply_ignores_unrelated_messages(db):
    user = User(email="a@b.c", password_hash="x", name="T")
    db.add(user)
    db.commit()
    assert cp.apply_chat_message(db, user.id, "Как восстановиться после пробежки?") == {}
    assert db.query(PlanPreference).count() == 0
