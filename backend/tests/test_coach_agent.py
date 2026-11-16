"""Agent protocol and HTTP integration with real tools/SQLite, scripted model, no network.

The model is replaced at the transport boundary; validation, quota, history, proposal
publication and confirmation are the production code paths.
"""
import asyncio
import copy
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessage

from app.auth import create_access_token
from app.core.config import settings
from app.database import get_db
from app.main import app
from app.models import Activity, ApiUsage, ChatMessage, User, Workout
from app.services import coach_agent as agent

MONDAY = date(2026, 11, 2)
TODAY = date(2026, 11, 4)


@pytest.fixture
def user(db):
    user = User(email="agent@example.com", password_hash="x", name="Runner",
        is_verified=True, onboarding_completed=True, timezone="Asia/Yekaterinburg",
        fitness_level="intermediate", running_goal="10k", weekly_km=25,
        training_days=4, easy_pace_min_km=6.5)
    db.add(user)
    # Actual Tuesday run is locked and contributes to the calendar week.
    db.flush()
    db.add(Activity(user_id=user.id, date=datetime(2026, 11, 3, 10, tzinfo=timezone.utc),
        distance_km=5.4, duration_min=34, pace_min_per_km=34 / 5.4, activity_type="run"))
    db.add(Activity(user_id=user.id, date=datetime(2026, 10, 25, 10, tzinfo=timezone.utc),
        distance_km=9, duration_min=60, pace_min_per_km=60 / 9, activity_type="run"))
    db.commit()
    return user


@pytest.fixture(autouse=True)
def isolated_agent(monkeypatch):
    monkeypatch.setattr(agent, "today_for", lambda u: TODAY)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def headers(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": str(user.id)})}


def candidate(km=5):
    return {"week_start": str(MONDAY), "requirements": {
        "training_days": 4, "min_session_km": 5, "long_run_date": "2026-11-06"},
        "workouts": [
            {"date": str(MONDAY + timedelta(days=i)), "workout_type": kind,
             "segments": [] if kind == "rest" else [{"kind": "run", "zone": "long" if kind == "long" else "easy",
                                                        "distance_km": km if kind != "long" else 8.5}]}
            for i, kind in [(2, "easy"), (3, "rest"), (4, "long"), (5, "rest"), (6, "easy")]]}


def ready_tools(user, db):
    tools = agent.CoachTools(user, db)
    tools.summary()
    tools.calendar(MONDAY)
    return tools


def model_response(*calls, text=None):
    payload = {"role": "assistant", "content": text}
    if calls:
        payload["tool_calls"] = [{"id": f"call_{i}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}
            for i, (name, args) in enumerate(calls)]
    return SimpleNamespace(choices=[SimpleNamespace(message=ChatCompletionMessage(**payload))],
                           usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50))


def script(monkeypatch, *responses):
    pending = list(responses)
    seen = []

    async def complete(messages):
        seen.append(copy.deepcopy(messages))
        assert pending, "unexpected extra model call"
        return pending.pop(0)

    monkeypatch.setattr(agent, "_completion", complete)
    return seen


def turn_script(monkeypatch, payload=None):
    return script(monkeypatch,
        model_response(("get_training_summary", {}), ("get_calendar", {"week_start": str(MONDAY)})),
        model_response(("preview_calendar_change", payload or candidate())),
        model_response(text="Подготовил предложение. Проверь даты перед подтверждением."))


def test_calendar_week_locks_actual_runs_and_counts_them(user, db):
    tools = ready_tools(user, db)
    calendar = tools.calendars[MONDAY]
    assert len(calendar["days"]) == 7
    assert calendar["days"][0]["locked"]
    assert calendar["days"][1]["locked"]
    assert calendar["days"][1]["workout"]["distance_km"] == 5.4
    result = tools.execute("preview_calendar_change", json.dumps(candidate()))
    assert result["status"] == "ready", result
    assert tools.draft["start"] == "2026-11-02T00:00:00"
    assert sum(w["distance_km"] or 0 for w in tools.draft["workouts"]) == 23.9
    assert tools.draft["workouts"][4]["workout_type"] == "long"
    assert db.query(Workout).count() == db.query(ApiUsage).count() == 0


@pytest.mark.parametrize("change,fragment", [
    (lambda p: p["workouts"][0]["segments"][0].update(distance_km=4), "меньше"),
    (lambda p: p["workouts"][0]["segments"][0].update(distance_km=50), "потолка"),
    (lambda p: p["requirements"].update(long_run_date="2026-11-08"), "Длинная"),
    (lambda p: p["workouts"][0].update(workout_type="rest", segments=[]), "тренировочных"),
    (lambda p: p["workouts"].append(p["workouts"][0]), "повторов"),
    (lambda p: p["workouts"][0].update(date="2026-11-03"), "заблокированных"),
])
def test_invalid_calendars_never_stage_or_write(user, db, change, fragment):
    tools = ready_tools(user, db)
    payload = candidate()
    change(payload)
    result = tools.execute("preview_calendar_change", json.dumps(payload))
    assert result["status"] in {"conflict", "error"}
    assert fragment in json.dumps(result, ensure_ascii=False)
    assert tools.draft is None
    assert db.query(Workout).count() == 0


def test_rejected_revision_discards_previously_staged_candidate(user, db):
    tools = ready_tools(user, db)
    assert tools.execute("preview_calendar_change", json.dumps(candidate()))["status"] == "ready"
    assert tools.execute("preview_calendar_change", json.dumps(candidate(50)))["status"] == "conflict"
    assert tools.draft is None


def test_requires_reads_and_scopes_activity_ownership(user, db):
    other = User(email="other@example.com", password_hash="x", name="Other")
    db.add(other)
    db.flush()
    activity = Activity(user_id=other.id, date=datetime.now(timezone.utc), distance_km=1, duration_min=7)
    db.add(activity)
    db.commit()
    tools = agent.CoachTools(user, db)
    assert tools.execute("preview_calendar_change", json.dumps(candidate()))["status"] == "error"
    assert tools.execute("get_activity_details", json.dumps({"activity_id": activity.id}))["status"] == "error"
    assert tools.execute("get_training_summary", '{"user_id": 123}')["status"] == "error"
    assert tools.execute("__import__", '{}')["status"] == "error"
    assert tools.execute("get_calendar", '{"week_start":"2026-11-03"}')["status"] == "error"


def test_adjacent_week_boundary_is_validated(user, db):
    # Next week Monday long immediately after Sunday long is prohibited.
    next_week = MONDAY + timedelta(days=7)
    db.add(Workout(user_id=user.id, planned_date=datetime(2026, 11, 8), day_of_week=6,
        workout_type="long", description="Long", distance_km=8.5))
    db.commit()
    tools = agent.CoachTools(user, db)
    tools.summary()
    tools.calendar(next_week)
    p = {"week_start": str(next_week), "requirements": {"training_days": 4}, "workouts": [
        {"date": str(next_week + timedelta(days=i)), "workout_type": "long" if i == 0 else "easy" if i in (2, 4, 6) else "rest",
         "segments": [{"kind": "run", "distance_km": 5}] if i in (0, 2, 4, 6) else []}
        for i in range(7)]}
    result = tools.execute("preview_calendar_change", json.dumps(p))
    assert result["status"] == "conflict"
    assert "границе" in str(result)


def test_http_tool_loop_propose_refine_confirm_without_double_plan_charge(client, user, db, monkeypatch):
    seen = turn_script(monkeypatch)
    first = client.post("/api/chat/message", headers=headers(user), json={"message": "Длинную в пятницу, минимум 5 км"})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["plan_draft"]["agent_version"] == 1
    assert db.query(Workout).count() == 0
    assert any(m["role"] == "tool" and '"status": "ready"' in m["content"] for m in seen[-1])
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 1

    seen = turn_script(monkeypatch)
    second = client.post("/api/chat/message", headers=headers(user), json={"message": "Проверь ещё раз"}).json()
    assert second["plan_draft"]["revision"] == 2
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 1
    assert db.query(ApiUsage).filter(ApiUsage.action == "chat").count() == 2
    calendar_result = next(json.loads(m["content"]) for m in seen[1]
                           if m["role"] == "tool" and '"latest_proposal"' in m["content"])
    assert calendar_result["latest_proposal"]["revision"] == 1
    assert client.post("/api/chat/plans/confirm", headers=headers(user), json={"message_id": body["id"]}).status_code == 404
    saved = client.post("/api/chat/plans/confirm", headers=headers(user), json={"message_id": second["id"]})
    assert saved.status_code == 200, saved.text
    rows = db.query(Workout).order_by(Workout.planned_date).all()
    assert len(rows) == 5  # Only Wed-Sun; past factual Tuesday is untouched.
    assert rows[2].planned_date.date() == date(2026, 11, 6)
    assert rows[2].workout_type == "long" and rows[2].distance_km == 8.5
    assert client.post("/api/chat/plans/confirm", headers=headers(user), json={"message_id": second["id"]}).status_code == 404
    assert db.query(Activity).filter(Activity.distance_km == 5.4).count() == 1


@pytest.mark.parametrize("mutation", ["calendar", "profile", "activity", "feedback", "tomorrow"])
def test_stale_confirmation_is_rejected_atomically(client, user, db, monkeypatch, mutation):
    turn_script(monkeypatch)
    body = client.post("/api/chat/message", headers=headers(user), json={"message": "Составь неделю"}).json()
    if mutation in {"calendar", "feedback"}:
        db.add(Workout(user_id=user.id, planned_date=datetime(2026, 11, 5), day_of_week=3,
            workout_type="easy", description="Existing", distance_km=5, rpe="hard" if mutation == "feedback" else None))
    elif mutation == "profile":
        db.get(User, user.id).weekly_km = 10
    elif mutation == "activity":
        db.query(Activity).filter(Activity.distance_km == 5.4).one().distance_km = 6
    else:
        monkeypatch.setattr(agent, "today_for", lambda u: TODAY + timedelta(days=1))
    db.commit()
    before = db.query(Workout).count()
    response = client.post("/api/chat/plans/confirm", headers=headers(user), json={"message_id": body["id"]})
    assert response.status_code == 409, response.text
    assert db.query(Workout).count() == before
    assert db.get(ChatMessage, body["id"]).context_type == "plan_proposal"


def test_plan_quota_failure_replaces_premature_model_promise(client, user, db, monkeypatch):
    db.add(ApiUsage(user_id=user.id, action="plan"))
    db.commit()
    turn_script(monkeypatch)
    body = client.post("/api/chat/message", headers=headers(user), json={"message": "Новая неделя"}).json()
    assert body["plan_draft"] is None
    assert "Лимит" in body["content"]
    assert "Подготовил" not in body["content"]
    assert db.query(Workout).count() == 0


def test_tool_failure_can_be_corrected_within_one_turn(client, user, db, monkeypatch):
    seen = script(monkeypatch,
        model_response(("get_training_summary", {}), ("get_calendar", {"week_start": str(MONDAY)})),
        model_response(("preview_calendar_change", candidate(4))),
        model_response(("preview_calendar_change", candidate())),
        model_response(text="Исправил короткие занятия, предложение готово."))
    response = client.post("/api/chat/message", headers=headers(user), json={"message": "Минимум 5 км"})
    assert response.json()["plan_draft"] is not None
    assert any('"status": "conflict"' in m.get("content", "") for m in seen[2])
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 1


def test_transport_failure_refunds_chat_and_does_not_fallback_or_change_calendar(client, user, db, monkeypatch):

    async def fail(messages):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(agent, "_completion", fail)
    r = client.post("/api/chat/message", headers=headers(user), json={"message": "Перенеси"})
    assert r.status_code == 200
    assert r.json()["id"] == 0
    assert db.query(Workout).count() == db.query(ApiUsage).count() == 0


def test_step_limit_does_not_publish_partial_proposal(client, user, db, monkeypatch):
    monkeypatch.setattr(settings, "COACH_AGENT_MAX_STEPS", 2)
    script(monkeypatch,
        model_response(("get_training_summary", {}), ("get_calendar", {"week_start": str(MONDAY)})),
        model_response(("preview_calendar_change", candidate())))
    r = client.post("/api/chat/message", headers=headers(user), json={"message": "Новый план"})
    assert r.json()["plan_draft"] is None
    assert db.query(ApiUsage).count() == 0


def test_refinement_retains_omitted_agreed_requirements(client, user, db, monkeypatch):
    turn_script(monkeypatch)
    first = client.post("/api/chat/message", headers=headers(user), json={"message": "Минимум 5 км"}).json()
    payload = candidate(4)
    payload.pop("requirements")
    turn_script(monkeypatch, payload)
    second = client.post("/api/chat/message", headers=headers(user), json={"message": "Пересмотри вариант"}).json()
    assert second["plan_draft"] is None
    assert "меньше согласованных 5" in second["content"]
    assert db.get(ChatMessage, first["id"]).context_type == "plan_proposal"
    assert db.query(ApiUsage).filter(ApiUsage.action == "plan").count() == 1


def test_preserves_completed_workout_and_protects_cross_user_confirmation(client, user, db, monkeypatch):
    completed = Workout(user_id=user.id, planned_date=datetime(2026, 11, 3), day_of_week=1,
                        workout_type="easy", description="Completed", distance_km=5.4,
                        completed=True, completion_status="completed")
    db.add(completed)
    other = User(email="intruder@example.com", password_hash="x", name="Other", is_verified=True)
    db.add(other)
    db.commit()
    completed_id = completed.id
    other_headers = headers(other)
    turn_script(monkeypatch)
    first = client.post("/api/chat/message", headers=headers(user), json={"message": "План"}).json()
    assert client.post("/api/chat/plans/confirm", headers=other_headers, json={"message_id": first["id"]}).status_code == 404
    assert client.post("/api/chat/plans/confirm", headers=headers(user), json={"message_id": first["id"]}).status_code == 200
    assert db.get(Workout, completed_id).description == "Completed"
    assert db.get(Workout, completed_id).completed


def test_success_text_comes_from_validated_calendar(client, user, monkeypatch):
    script(monkeypatch,
        model_response(("get_training_summary", {}), ("get_calendar", {"week_start": str(MONDAY)})),
        model_response(("preview_calendar_change", candidate())),
        model_response(text="Уже сохранил семь тренировок по 100 км!"))
    body = client.post("/api/chat/message", headers=headers(user), json={"message": "План"}).json()
    assert "23.9" in body["content"]
    assert "100 км" not in body["content"]
    assert "после подтверждения" in body["content"]


@pytest.mark.parametrize("premium", [False, True])
def test_all_users_use_agent_without_switch(client, user, db, monkeypatch, premium):
    db.get(User, user.id).is_premium = premium
    db.commit()
    script(monkeypatch, model_response(text="Agent reply"))
    response = client.post("/api/chat/message", headers=headers(user), json={"message": "Hi"})
    assert response.status_code == 200
    assert response.json()["content"] == "Agent reply"


def test_retired_switches_in_old_dotenv_do_not_break_startup(tmp_path):
    from app.core.config import Settings

    old_env = tmp_path / "old.env"
    old_env.write_text("COACH_AGENT_ENABLED=false\nCOACH_AGENT_USER_IDS=99999\n", encoding="utf-8")
    parsed = Settings(_env_file=old_env, SECRET_KEY="test-retired-config-key")
    assert not hasattr(parsed, "COACH_AGENT_ENABLED")
    assert not hasattr(parsed, "COACH_AGENT_USER_IDS")
    assert parsed.COACH_AGENT_MAX_STEPS == 6


def test_deepseek_transport_sends_tools_and_preserves_protocol(monkeypatch):
    provider = {"name": "deepseek", "model": "configured-model"}
    monkeypatch.setattr(agent.ai_agent, "_providers", lambda: [provider])
    monkeypatch.setattr(agent.ai_agent, "_client_for", lambda p: "client")
    captured = {}

    async def request(client, **kwargs):
        captured.update(kwargs)
        return "response"

    monkeypatch.setattr(agent.ai_agent, "_acreate", request)
    assert asyncio.run(agent._completion([{"role": "user", "content": "Hi"}])) == "response"
    assert captured["model"] == "configured-model"
    assert captured["tools"] == agent.TOOLS
    assert captured["extra_body"]["thinking"]["type"] == "disabled"
    assert "response_format" not in captured
