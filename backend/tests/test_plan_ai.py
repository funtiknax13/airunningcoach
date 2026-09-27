import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import plan_ai as ai
from app.services import plan_format as pf
from app.services import planner as pl
from app.services.zones import build_zones
from tests.conftest import make_user, NOW

MONDAY = datetime(2026, 9, 28)


def req_for(days=7, **kw):
    user = kw.pop("user", None) or make_user(easy_pace_min_km=7.0)
    base = dict(start=MONDAY, days=days, zones=build_zones(user, [], NOW), training_days=4,
                level="intermediate", goal="10k", weekly_km_profile=20.0, longest_run_km=10.0)
    base.update(kw)
    return pl.PlanRequest(**base)


def resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def run_seg(km, zone="easy"):
    return {"kind": "run", "zone": zone, "distance_km": km}


def day(t, *segs, comment="ok"):
    return {"workout_type": t, "segments": list(segs), "comment": comment}


REST = {"workout_type": "rest", "segments": [], "comment": None}


def good_week():
    return [day("easy", run_seg(4)), REST, day("tempo", {"kind": "warmup", "distance_km": 1},
            {"kind": "steady", "zone": "tempo", "distance_km": 3}, {"kind": "cooldown", "distance_km": 1}),
            REST, day("easy", run_seg(4)), REST, day("long", run_seg(8, "long"))]


class FakeChat:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    async def __call__(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return resp(r if isinstance(r, str) else json.dumps({"plan": r}))


def run(coro):
    return asyncio.run(coro)


def gen(req, chat, **kw):
    return run(ai.generate(req, context="CTX", chat_context="", chat=chat, system="SYS", **kw))


def test_parse_days_variants_and_errors():
    assert len(ai.parse_days(json.dumps({"plan": good_week()}), 7)) == 7
    assert len(ai.parse_days(json.dumps(good_week()), 7)) == 7
    with pytest.raises(pf.PlanFormatError):
        ai.parse_days(json.dumps({"plan": good_week()[:5]}), 7)
    with pytest.raises(ValueError):
        ai.parse_days("not json", 7)


def test_happy_path_source_ai_and_numbers_from_zones():
    chat = FakeChat(good_week())
    out = gen(req_for(), chat)
    assert out.source == "ai" and out.reason is None and len(out.workouts) == 7
    tempo = next(w for w in out.workouts if w["workout_type"] == "tempo")
    assert tempo["plan_source"] == "ai" and tempo["target_pace_min_km"]
    # средний темп совпадает с расчётом по отрезкам, а не с числом, выдуманным моделью
    assert tempo["target_pace_min_km"] == tempo["plan_structure"]["resolved"]["avg_pace"]
    assert len(chat.calls) == 1
    assert chat.calls[0]["response_format"] == {"type": "json_object"}
    prompt = chat.calls[0]["messages"][1]["content"]
    assert "ровно 4 тренировочных дней" in prompt and "воскресенье" in prompt
    assert "НЕ пиши" in prompt and "CTX" in prompt


def test_invalid_then_valid_retries_once_with_error_feedback():
    chat = FakeChat("not json at all", good_week())
    out = gen(req_for(), chat)
    assert out.source == "ai" and len(chat.calls) == 2
    assert "отклонён" in chat.calls[1]["messages"][1]["content"]


def test_two_invalid_answers_fall_back_to_rules():
    chat = FakeChat("nope", json.dumps({"plan": [{"workout_type": "sprint"}] * 7}))
    out = gen(req_for(), chat)
    assert out.source == "rules" and out.reason == "invalid" and len(out.workouts) == 7
    assert all(w["plan_source"] == "rules" for w in out.workouts)


def test_provider_failure_falls_back_without_retry(monkeypatch):
    monkeypatch.setattr(ai, "RETRY_DELAY_S", 0)
    chat = FakeChat(RuntimeError("all providers down"))
    out = gen(req_for(), chat)
    assert out.source == "rules" and out.reason == "ai_failed" and len(chat.calls) == 1   # не «временный» сбой


def test_transient_503_is_retried_once_then_succeeds(monkeypatch):
    monkeypatch.setattr(ai, "RETRY_DELAY_S", 0)
    chat = FakeChat(RuntimeError("Error code: 503 - high demand"), good_week())
    out = gen(req_for(), chat)
    assert out.source == "ai" and len(chat.calls) == 2


def test_quota_429_is_not_retried(monkeypatch):
    monkeypatch.setattr(ai, "RETRY_DELAY_S", 0)
    chat = FakeChat(RuntimeError("Error code: 429 - quota exceeded"), good_week())
    out = gen(req_for(), chat)
    assert out.source == "rules" and out.reason == "ai_failed" and len(chat.calls) == 1


def test_transient_failure_twice_falls_back(monkeypatch):
    monkeypatch.setattr(ai, "RETRY_DELAY_S", 0)
    chat = FakeChat(RuntimeError("503 unavailable"), RuntimeError("503 unavailable"))
    assert gen(req_for(), chat).source == "rules"


def test_no_ai_configured_uses_rules():
    out = gen(req_for(), None)
    assert out.source == "rules" and out.reason == "no_ai"
    assert gen(req_for(), FakeChat(good_week()), ai_enabled=False).reason == "no_ai"


def test_beginner_is_algorithmic_by_design_without_calling_ai():
    chat = FakeChat(good_week())
    r = req_for(level="beginner", weekly_km_profile=0.0, zones=build_zones(make_user(), [], NOW))
    out = gen(r, chat)
    assert out.source == "algo" and out.reason == "beginner" and not chat.calls


def test_ai_plan_is_clamped_to_training_days_and_volume():
    overloaded = [day("easy", run_seg(15)), day("easy", run_seg(15)), day("easy", run_seg(15)),
                  day("easy", run_seg(15)), day("easy", run_seg(15)), day("long", run_seg(30, "long")),
                  day("easy", run_seg(15))]
    r = req_for()
    out = gen(r, FakeChat(overloaded))
    assert out.source == "ai"
    active = [w for w in out.workouts if w["workout_type"] != "rest"]
    assert len(active) == 4                              # 7 дней -> ровно 4
    total = sum(w["distance_km"] for w in active)
    cap = pl.week_target_km(r, 0, datetime(2026, 9, 28).date()) * pl.WEEK_CAP_TOLERANCE
    assert total <= cap + 2.0


def test_quality_removed_when_zones_unknown():
    r = req_for(zones=build_zones(make_user(), [], NOW))
    out = gen(r, FakeChat(good_week()))
    assert out.source == "ai"
    assert not {w["workout_type"] for w in out.workouts} & {"tempo", "interval"}


def test_month_plan_is_chunked_and_assembled():
    week = good_week()
    chat = FakeChat(week + week, week + week)             # 2 куска по 14 дней
    out = gen(req_for(days=28), chat)
    assert out.source == "ai" and len(out.workouts) == 28 and len(chat.calls) == 2
    assert "Предыдущие дни" in chat.calls[1]["messages"][1]["content"]


def test_month_falls_back_wholly_if_any_chunk_fails():
    week = good_week()
    chat = FakeChat(week + week, RuntimeError("down"))
    out = gen(req_for(days=28), chat)
    assert out.source == "rules" and len(out.workouts) == 28
    assert {w["plan_source"] for w in out.workouts} == {"rules"}   # без смеси AI и правил


def test_prompt_gives_volume_target_long_range_and_quality_hint():
    r = req_for(start=MONDAY, history_avg_km=17.0, history_runs_4w=8, longest_run_km=10.0)
    prompt = ai.build_prompt(r, "CTX", "", 0, 7, [])
    assert "недельный объём около" in prompt and "длинная 7–" in prompt
    assert "качественная тренировка недели" in prompt
