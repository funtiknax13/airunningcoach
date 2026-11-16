"""Regression checks for the historical allowance, independently of plan targets."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models import Activity, User
from app.services import coach_agent, plan_ai, plan_service, planner as pl
from app.services.zones import build_zones
from tests.conftest import make_user

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)  # Monday
MONDAY = NOW.replace(hour=0)


def run(when, km, kind="run"):
    return SimpleNamespace(date=when, distance_km=km, duration_min=km * 6,
        pace_min_per_km=6, activity_type=kind, effort=None, max_heart_rate=None)


def history(volumes):
    # First record on a Monday establishes the first fully observed week.
    return [run(MONDAY - timedelta(weeks=len(volumes) - i), km)
            for i, km in enumerate(volumes) if km > 0]


def request(volumes):
    return pl.PlanRequest(start=MONDAY.replace(tzinfo=None), days=28,
        zones=build_zones(make_user(easy_pace_min_km=6.5), [], NOW),
        training_days=4, level="intermediate", goal="10k", weekly_km_profile=25,
        completed_week_km=volumes)


FORMULA_CASES = [
    # label, completed weeks, profile, median, last week, cap
    ("user_chart", [11, 14, 19, 19, 23], 25, 19, 23, 27.6),
    ("steady", [25, 25, 25, 25, 25, 25], 25, 25, 25, 31.25),
    ("growth", [20, 22, 24, 26, 28, 30], 25, 25, 30, 36),
    ("deload", [25, 26, 27, 28, 29, 18], 25, 26.5, 18, 33.125),
    ("long_pause_stale_profile", [25, 0, 0, 0, 0, 0], 60, 0, 0, 15),
    ("small_volumes", [2, 3, 4, 5, 6, 7], 0, 4.5, 7, 15),
    ("experienced_history", [60, 60, 60, 60, 60, 60], 10, 60, 60, 75),
    ("single_spike", [20, 20, 20, 20, 20, 50], 20, 20, 50, 60),
    ("experienced_new_user", [], 60, None, None, 72),
    ("unknown_new_user", [], None, None, None, 15),
]


@pytest.mark.parametrize("label,volumes,profile,middle,recent,cap", FORMULA_CASES,
                         ids=[c[0] for c in FORMULA_CASES])
def test_formula(label, volumes, profile, middle, recent, cap):
    r = request(volumes)
    r.weekly_km_profile = profile
    policy = pl.week_load_policy(r)
    assert policy["median_km"] == middle
    assert policy["last_week_km"] == recent
    assert policy["cap_km"] == pytest.approx(cap)
    assert pl.week_cap_km(r, 0, MONDAY.date()) == pytest.approx(cap)
    assert pl.compute_constraints(r)["weeks"][0]["cap_km"] == pytest.approx(cap)


def test_completed_calendar_weeks_include_zero_but_exclude_current_week():
    runs = history([25, 25, 25, 25, 25, 0])
    runs += [run(NOW, 100), run(NOW + timedelta(days=1), 1000), run(MONDAY - timedelta(days=3), 200, "ride")]
    stats = pl.history_stats(runs, NOW)
    assert [w["distance_km"] for w in stats["completed_weeks"]] == [25, 25, 25, 25, 25, 0]
    assert len(stats["completed_weeks"]) == 6


def test_entry_week_and_weeks_before_observation_are_not_invented():
    first = MONDAY - timedelta(weeks=3) + timedelta(days=2)
    runs = [run(first, 5), run(first + timedelta(days=7), 10)]
    weeks = pl.completed_week_volumes(runs, NOW)
    assert [w["distance_km"] for w in weeks] == [10, 0]
    assert pl.week_load_policy(request([10, 0]))["history_sufficient"] is False


def test_week_boundary_uses_user_timezone_and_counts_short_runs():
    # Sunday UTC, Monday in Yekaterinburg: belongs to the incomplete current week.
    first = datetime(2026, 10, 26, 0, tzinfo=timezone.utc)
    boundary = datetime(2026, 11, 15, 21, tzinfo=timezone.utc)
    runs = [run(first, 10), run(boundary, 100), run(datetime(2026, 11, 10, tzinfo=timezone.utc), 0.5)]
    local = pl.completed_week_volumes(runs, NOW, "Asia/Yekaterinburg")
    utc = pl.completed_week_volumes(runs, NOW, "UTC")
    assert local[-1]["distance_km"] == 0.5
    assert utc[-1]["distance_km"] == 100.5
    assert pl.completed_week_volumes(runs, NOW, "Invalid/Timezone") == utc


def test_last_week_can_raise_allowance_even_when_it_is_a_spike():
    stats = pl.history_stats(history([20, 20, 20, 20, 20, 50]), NOW)
    volumes = [w["distance_km"] for w in stats["completed_weeks"]]
    assert pl.week_load_policy(request(volumes))["cap_km"] == 60


def test_target_and_ceiling_are_separate_and_future_dates_do_not_inflate_ceiling():
    r = request([20, 22, 24, 26, 28, 30])
    constraints = pl.compute_constraints(r)
    assert all(w["cap_km"] == 36 for w in constraints["weeks"])
    assert constraints["weeks"][3]["deload"]
    assert pl.week_target_km(r, 3, (MONDAY + timedelta(weeks=3)).date()) < pl.week_target_km(r, 2, (MONDAY + timedelta(weeks=2)).date())
    assert "верх 36" in plan_ai._weeks_lines(r, 0, 28)


def test_cold_start_uses_profile_plus_twenty_percent_and_exposes_missing_history():
    r = request([])
    assert pl.week_load_policy(r)["source"] == "profile"
    assert pl.week_load_policy(r)["history_sufficient"] is False
    assert pl.week_cap_km(r, 0, MONDAY.date()) == pytest.approx(30)
    assert pl.week_load_policy(request([20, 22]))["cap_km"] == 30


def test_agent_allows_peak_above_old_average_ceiling_and_rechecks_on_confirm(db, monkeypatch):
    user = User(email="load@example.com", password_hash="x", name="Runner", timezone="UTC",
        weekly_km=25, training_days=4, fitness_level="intermediate", running_goal="10k",
        easy_pace_min_km=6.5)
    db.add(user)
    db.flush()
    for i, km in enumerate([20, 22, 24, 26, 28, 30]):
        for offset in (0, 2, 4, 6):
            when = MONDAY - timedelta(weeks=6-i) + timedelta(days=offset)
            db.add(Activity(user_id=user.id, date=when, distance_km=km/4,
                            duration_min=km/4*6.5, activity_type="run"))
    db.commit()
    original = plan_service.build_request

    def fixed_now(user, db, start, days, now=None):
        return original(user, db, start, days, now=NOW)

    monkeypatch.setattr(plan_service, "build_request", fixed_now)
    monkeypatch.setattr(coach_agent, "today_for", lambda u: NOW.date())
    tools = coach_agent.CoachTools(user, db)
    tools.summary()
    calendar = tools.calendar(MONDAY.date())
    assert calendar["limits"]["weekly_load_policy"]["completed_week_km"] == [20, 22, 24, 26, 28, 30]
    assert calendar["limits"]["weeks"][0]["cap_km"] == 36
    payload = {"week_start": str(MONDAY.date()), "requirements": {"training_days": 4}, "workouts": [
        {"date": str((MONDAY + timedelta(days=i)).date()),
         "workout_type": "easy" if i in (0, 2, 4, 6) else "rest",
         "segments": [{"kind": "run", "zone": "easy", "distance_km": 8}] if i in (0, 2, 4, 6) else []}
        for i in range(7)]}
    result = tools.execute("preview_calendar_change", json.dumps(payload))
    assert result["status"] == "ready", result
    assert sum(w["distance_km"] or 0 for w in tools.draft["workouts"]) == 32
    coach_agent.confirm(tools.draft, user, db)
    db.commit()
    assert db.query(Activity).count() == 24
    from app.models import Workout
    assert sum(w.distance_km or 0 for w in db.query(Workout)) == 32


def test_envelope_uses_same_weekly_cap_as_agent():
    r = request([20, 20, 20, 20, 20, 20])
    r.days = 7
    days = [{"workout_type": "easy", "segments": [{"kind": "run", "zone": "easy", "distance_km": 9}]} if i in (0, 2, 4, 6)
            else {"workout_type": "rest", "segments": []} for i in range(7)]
    out = pl.enforce_envelope(days, r)
    from app.services import plan_format as pf
    assert sum(pf.day_distance_km(d, r.zones) or 0 for d in out) <= 25.5  # half-km rounding
