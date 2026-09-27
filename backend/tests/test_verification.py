"""Проверка выполнения тренировки относительно плана (verdict_for) на плане в формате отрезков."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models import Workout
from app.services import plan_format as pf
from app.services.workout_verification import verdict_for, DEVIATION_OK, DEVIATION_PARTIAL
from app.services.zones import build_zones


def _zones(easy):
    user = SimpleNamespace(easy_pace_min_km=easy, race_distance_km=None, race_time_min=None,
                           max_hr=None, rest_hr=None, age=35)
    return build_zones(user, [], datetime.now(timezone.utc))


def _workout(day, zones):
    w = pf.build_workout(pf.normalize_day(day), zones, "rules")
    return Workout(workout_type=w["workout_type"], description=w["description"], distance_km=w["distance_km"],
                   duration_min=w["duration_min"], target_pace_min_km=w["target_pace_min_km"],
                   plan_structure=w["plan_structure"])


def _act(km, pace=None, minutes=None, analysis=None):
    minutes = minutes if minutes is not None else km * pace
    return SimpleNamespace(distance_km=km, duration_min=minutes, pace_min_per_km=minutes / km,
                           analysis=analysis)


Z = _zones(7.5)
EASY = _workout({"workout_type": "easy", "segments": [{"kind": "run", "zone": "easy", "distance_km": 3.5}]}, Z)
TEMPO = _workout({"workout_type": "tempo", "segments": [
    {"kind": "warmup", "distance_km": 1}, {"kind": "steady", "zone": "tempo", "distance_km": 4},
    {"kind": "cooldown", "distance_km": 1}]}, Z)
INTERVALS = _workout({"workout_type": "interval", "segments": [
    {"kind": "warmup", "distance_km": 1},
    {"kind": "intervals", "reps": 5, "distance_m": 400, "recovery": {"distance_m": 200, "zone": "recovery"}},
    {"kind": "cooldown", "distance_km": 1}]}, Z)
BEGINNER = _workout({"workout_type": "easy", "segments": [
    {"kind": "walk", "duration_min": 5},
    {"kind": "run_walk", "reps": 8, "run_s": 60, "walk_s": 90},
    {"kind": "walk", "duration_min": 5}]}, _zones(None))


def reps(n, pace):
    return {"intervals": {"kind": "intervals", "reps": [{"pace_min_km": pace}] * n}}


CASES = [
    ("easy on plan", EASY, lambda: _act(3.5, 7.67), "completed"),
    ("easy slightly fast", EASY, lambda: _act(3.5, 7.17), "completed"),
    ("easy slow edge of range", EASY, lambda: _act(3.5, 8.08), "completed"),
    ("easy too fast", EASY, lambda: _act(3.5, 6.5), "approximate"),
    ("easy all out", EASY, lambda: _act(3.5, 4.5), "unconfirmed"),
    ("easy 3.0 of 3.5 km", EASY, lambda: _act(3.0, 7.67), "approximate"),
    ("easy 1.5 of 3.5 km", EASY, lambda: _act(1.5, 7.67), "unconfirmed"),
    ("tempo average as planned", TEMPO, lambda: _act(6.0, TEMPO.target_pace_min_km), "completed"),
    ("tempo run entirely easy", TEMPO, lambda: _act(6.0, 7.67), "approximate"),
    ("tempo only 3 km", TEMPO, lambda: _act(3.0, TEMPO.target_pace_min_km), "unconfirmed"),
    ("intervals without analysis: volume+pace only", INTERVALS, lambda: _act(5.0, INTERVALS.target_pace_min_km), "completed"),
    ("intervals 5 reps as planned", INTERVALS, lambda: _act(5.0, INTERVALS.target_pace_min_km, analysis=reps(5, 5.6)), "completed"),
    ("intervals 2 of 5 reps", INTERVALS, lambda: _act(5.0, INTERVALS.target_pace_min_km, analysis=reps(2, 5.6)), "unconfirmed"),
    ("beginner 28 min", BEGINNER, lambda: _act(2.8, minutes=28), "completed"),
    ("beginner only 10 of 28 min (regression)", BEGINNER, lambda: _act(1.0, minutes=10), "unconfirmed"),
    ("beginner 26 of 28 min", BEGINNER, lambda: _act(2.6, minutes=26), "approximate"),
]


@pytest.mark.parametrize("name,workout,activity,expected", CASES, ids=[c[0] for c in CASES])
def test_verdict(name, workout, activity, expected):
    assert verdict_for(activity(), workout) == expected


def test_no_activity_is_unconfirmed():
    assert verdict_for(None, EASY) == "unconfirmed"


def test_thresholds_are_relative():
    assert DEVIATION_OK == 0.07 and DEVIATION_PARTIAL == 0.30
    assert verdict_for(_act(3.5 * 1.06, 7.67), EASY) == "completed"     # +6% дистанции — чисто
    assert verdict_for(_act(3.5 * 1.20, 7.67), EASY) == "approximate"   # +20% — частично
    assert verdict_for(_act(3.5 * 1.40, 7.67), EASY) == "unconfirmed"   # +40% — не подтверждена


def test_time_based_matching_prefers_closest_duration(db):
    from app.models import Activity, User
    from app.services.workout_verification import find_matching_activity_for_workout
    user = User(email="v@example.com", password_hash="x", name="V", timezone="UTC")
    db.add(user)
    db.commit()
    when = datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)
    near = Activity(user_id=user.id, date=when, distance_km=2.9, duration_min=29, pace_min_per_km=10, activity_type="run")
    far = Activity(user_id=user.id, date=when, distance_km=1.0, duration_min=10, pace_min_per_km=10, activity_type="run")
    db.add_all([far, near])
    w = _workout({"workout_type": "easy", "segments": [
        {"kind": "walk", "duration_min": 5},
        {"kind": "run_walk", "reps": 8, "run_s": 60, "walk_s": 90},
        {"kind": "walk", "duration_min": 5}]}, _zones(None))
    w.user_id, w.planned_date, w.day_of_week = user.id, datetime(2026, 9, 28), 0
    db.add(w)
    db.commit()
    assert find_matching_activity_for_workout(w, user.id, db, "UTC").id == near.id
