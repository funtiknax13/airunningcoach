"""Сквозные проверки через HTTP: профиль, генерация плана, зоны, чат-пожелания,
самокалибровка. ИИ не вызывается (ключей нет — STUB-режим; чат подменяем в тестах)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.database import get_db
from app.main import app
from app.models import ApiUsage, ChatMessage, PlanPreference, User, Workout


@pytest.fixture
def client(db, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db
    # фоновый AI-разбор пробежек ходит в отдельную сессию/сеть — в тестах не нужен
    monkeypatch.setattr("app.routers.activities.analyze_new_activity", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.training.analyze_workout_completion", lambda *a, **k: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_db_user(db, **kw):
    base = dict(email="u@example.com", password_hash="x", name="Тест", is_verified=True,
                fitness_level="intermediate", running_goal="10k", weekly_km=20.0,
                training_days=4, timezone="UTC", onboarding_completed=True, age=35)
    base.update(kw)
    user = User(**base)
    db.add(user)
    db.commit()
    return user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


def add_run(client, user, days_ago, km, pace, **extra):
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    r = client.post("/api/activities", headers=auth(user),
                    json={"date": when, "distance_km": km, "duration_min": round(km * pace, 2), **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_profile_accepts_hr_and_pace_and_validates(client, db):
    user = make_db_user(db)
    r = client.patch("/api/auth/me", headers=auth(user),
                     json={"max_hr": 190, "rest_hr": 60, "easy_pace_min_km": 7.5})
    assert r.status_code == 200
    body = r.json()
    assert body["max_hr"] == 190 and body["rest_hr"] == 60 and body["easy_pace_min_km"] == 7.5
    assert client.patch("/api/auth/me", headers=auth(user), json={"max_hr": 400}).status_code == 422
    assert client.patch("/api/auth/me", headers=auth(user), json={"easy_pace_min_km": 1.0}).status_code == 422


def test_zones_endpoint_reports_unknown_then_known(client, db):
    user = make_db_user(db, age=None)
    z = client.get("/api/training/zones", headers=auth(user)).json()
    assert z["zones"]["pace_confidence"] == "none" and z["data_status"]["needs_data"] is True
    client.patch("/api/auth/me", headers=auth(user), json={"easy_pace_min_km": 7.83})
    z = client.get("/api/training/zones", headers=auth(user)).json()
    assert z["zones"]["pace_source"] == "profile" and z["zones"]["pace"]["tempo"] is not None
    assert z["training_days"] == 4


def test_week_plan_without_ai_is_rules_saved_in_v2_and_refunds_quota(client, db):
    user = make_db_user(db, easy_pace_min_km=7.83)
    r = client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done" and body["source"] == "rules" and body["reason"] == "no_ai"
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 0     # попытка возвращена

    workouts = client.get("/api/training/workouts", headers=auth(user)).json()
    assert len(workouts) == 7
    active = [w for w in workouts if w["workout_type"] != "rest"]
    assert len(active) == 4                                   # ровно число дней из профиля
    assert all(w["plan_source"] == "rules" for w in workouts)
    w = next(w for w in active if w["plan_structure"])
    assert w["plan_structure"]["version"] == 2
    assert w["plan_structure"]["resolved"]["segments"]
    # плашка = среднее из отрезков, а не выдуманное число
    assert w["target_pace_min_km"] == w["plan_structure"]["resolved"]["avg_pace"]


def test_second_generation_is_not_blocked_by_daily_limit_when_ai_unused(client, db):
    user = make_db_user(db)
    for _ in range(3):        # у Basic лимит 1 план в день, но ИИ не тратился
        assert client.post("/api/training/plans/generate?weeks=1", headers=auth(user)).status_code == 200


def test_beginner_gets_time_based_run_walk_plan_marked_algo(client, db):
    user = make_db_user(db, fitness_level="beginner", weekly_km=0.0, training_days=3,
                        running_goal="fitness")
    body = client.post("/api/training/plans/generate?weeks=1", headers=auth(user)).json()
    assert body["source"] == "algo" and body["reason"] == "beginner"
    workouts = client.get("/api/training/workouts", headers=auth(user)).json()
    first = next(w for w in workouts if w["workout_type"] != "rest")
    kinds = [s["kind"] for s in first["plan_structure"]["segments"]]
    assert kinds == ["walk", "run_walk", "walk"]
    assert first["plan_structure"]["resolved"]["distance_km"] is None       # без зон дистанцию не выдумываем
    assert first["duration_min"] and first["target_pace_min_km"] is None


def test_new_run_recalibrates_future_workouts(client, db):
    user = make_db_user(db, age=None)
    client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    before = client.get("/api/training/workouts", headers=auth(user)).json()
    easy = next(w for w in before if w["workout_type"] == "easy")
    assert easy["target_pace_min_km"] is None                 # зоны неизвестны -> темпа нет

    for d in (2, 5, 8):                                       # три пробежки → зоны из истории
        add_run(client, user, d, 5, 7.5)
    after = client.get("/api/training/workouts", headers=auth(user)).json()
    easy_after = next(w for w in after if w["id"] == easy["id"])
    assert easy_after["target_pace_min_km"] is not None
    assert 7.0 < easy_after["target_pace_min_km"] < 8.5
    assert easy_after["plan_structure"]["resolved"]["pace_confidence"] == "medium"


def test_profile_change_recalibrates_and_completed_workouts_stay_frozen(client, db):
    user = make_db_user(db, easy_pace_min_km=8.5)
    client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    ws = client.get("/api/training/workouts", headers=auth(user)).json()
    active = [w for w in ws if w["workout_type"] != "rest"]
    frozen, moving = active[0], active[1]
    row = db.get(Workout, frozen["id"])
    row.completion_status, row.completed = "completed", True
    db.commit()

    client.patch("/api/auth/me", headers=auth(user), json={"easy_pace_min_km": 6.0})
    after = {w["id"]: w for w in client.get("/api/training/workouts", headers=auth(user)).json()}
    assert after[frozen["id"]]["target_pace_min_km"] == frozen["target_pace_min_km"]     # снимок
    assert after[moving["id"]]["target_pace_min_km"] < moving["target_pace_min_km"]      # пересчитан


def test_feedback_endpoint_saves_rpe(client, db):
    user = make_db_user(db, easy_pace_min_km=7.5)
    client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    w = next(w for w in client.get("/api/training/workouts", headers=auth(user)).json()
             if w["workout_type"] != "rest")
    assert client.post(f"/api/training/workouts/{w['id']}/feedback", headers=auth(user),
                       json={"rpe": "hard"}).json() == {"rpe": "hard"}
    assert db.get(Workout, w["id"]).rpe == "hard"
    assert client.post(f"/api/training/workouts/{w['id']}/feedback", headers=auth(user),
                       json={"rpe": "brutal"}).status_code == 422
    assert client.post("/api/training/workouts/99999/feedback", headers=auth(user),
                       json={"rpe": "ok"}).status_code == 404


def test_chat_wish_is_saved_hint_appended_and_profile_edit_resets_it(client, db, monkeypatch):
    user = make_db_user(db, training_days=3)

    async def fake_reply(message, user, db_, history, lang="ru", plan_just_regenerated=False):
        return "Хорошо, записал."

    monkeypatch.setattr("app.routers.chat.chat_response", fake_reply)
    r = client.post("/api/chat/message", headers=auth(user),
                    json={"message": "Хочу тренироваться 5 раз в неделю", "lang": "ru"})
    assert r.status_code == 200
    text = r.json()["content"]
    assert text.startswith("Хорошо, записал.") and "В профиле сейчас указано 3 дн." in text
    assert db.query(PlanPreference).one().training_days == 5
    # сохранённый в историю ответ содержит подсказку
    assert "Профиль → Тренировки" in db.query(ChatMessage).filter(ChatMessage.role == "ai").one().content

    # пожелание из чата действует в плане: 5 дней вместо 3 из профиля
    client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    ws = client.get("/api/training/workouts", headers=auth(user)).json()
    assert len([w for w in ws if w["workout_type"] != "rest"]) in (5, 6)

    # пользователь пересмотрел профиль -> профиль снова главный
    client.patch("/api/auth/me", headers=auth(user), json={"training_days": 3})
    assert db.query(PlanPreference).one().training_days is None
    client.post("/api/training/plans/generate?weeks=1", headers=auth(user))
    ws = client.get("/api/training/workouts", headers=auth(user)).json()
    assert len([w for w in ws if w["workout_type"] != "rest"]) == 3


def test_no_hint_when_chat_wish_matches_profile(client, db, monkeypatch):
    user = make_db_user(db, training_days=4)

    async def fake_reply(*a, **k):
        return "Ок."

    monkeypatch.setattr("app.routers.chat.chat_response", fake_reply)
    r = client.post("/api/chat/message", headers=auth(user),
                    json={"message": "Хочу 4 раза в неделю"})
    assert r.json()["content"] == "Ок."


def test_ai_outage_message_is_not_saved_and_quota_refunded(client, db):
    user = make_db_user(db)                       # ключей нет -> chat_response вернёт «недоступен»
    r = client.post("/api/chat/message", headers=auth(user), json={"message": "Привет"})
    assert r.status_code == 200 and "недоступен" in r.json()["content"]
    assert db.query(ChatMessage).filter(ChatMessage.role == "ai").count() == 0
    assert db.query(ApiUsage).filter(ApiUsage.action == "chat").count() == 0


def test_activity_effort_is_stored_and_validated(client, db):
    user = make_db_user(db)
    a = add_run(client, user, 1, 5, 6.0, effort="hard")
    assert a["effort"] == "hard"
    bad = client.post("/api/activities", headers=auth(user),
                      json={"date": datetime.now(timezone.utc).isoformat(), "distance_km": 5,
                            "duration_min": 30, "effort": "medium"})
    assert bad.status_code == 422


def test_month_plan_requires_premium(client, db):
    user = make_db_user(db)
    assert client.post("/api/training/plans/generate?weeks=4", headers=auth(user)).status_code == 403
