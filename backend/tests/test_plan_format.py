import pytest

from app.services import plan_format as pf
from app.services.zones import build_zones
from tests.conftest import make_user, NOW

TEMPO_DAY = {
    "workout_type": "tempo",
    "segments": [
        {"kind": "warmup", "distance_km": 1},
        {"kind": "steady", "distance_km": 4, "zone": "tempo"},
        {"kind": "cooldown", "distance_km": 1},
    ],
    "comment": "  Держи ровно.  ",
}


def zones_for(easy=7 + 50 / 60, **kw):
    return build_zones(make_user(easy_pace_min_km=easy, **kw), [], NOW)


def test_normalize_day_fills_default_zones_and_trims_comment():
    day = pf.normalize_day(TEMPO_DAY)
    assert [s["zone"] for s in day["segments"]] == ["easy", "tempo", "easy"]
    assert day["comment"] == "Держи ровно."


def test_rest_day_has_no_segments():
    day = pf.normalize_day({"workout_type": "rest", "segments": [{"kind": "run", "distance_km": 5}]})
    assert day == {"workout_type": "rest", "segments": [], "comment": None}


def test_legacy_flat_easy_shape_is_accepted():
    day = pf.normalize_day({"workout_type": "easy", "distance_km": 6, "target_pace_min_km": 5.5})
    assert day["segments"] == [{"kind": "run", "zone": "easy", "distance_km": 6.0}]


@pytest.mark.parametrize("raw", [
    "not a dict",
    {"workout_type": "sprint", "segments": []},
    {"workout_type": "easy", "segments": []},
    {"workout_type": "tempo", "distance_km": 6},                      # у темповой плоской формы нет
    {"workout_type": "easy", "segments": [{"kind": "run"}]},
    {"workout_type": "easy", "segments": [{"kind": "run", "distance_km": 900}]},
    {"workout_type": "easy", "segments": [{"kind": "run", "distance_km": 5, "zone": "warp"}]},
    {"workout_type": "interval", "segments": [{"kind": "intervals", "reps": 6}]},
    {"workout_type": "easy", "segments": [{"kind": "dance", "distance_km": 5}]},
])
def test_invalid_days_rejected(raw):
    with pytest.raises(pf.PlanFormatError):
        pf.normalize_day(raw)


def test_resolve_average_pace_is_time_over_distance_and_consistent():
    """Регрессия: плашка 5:24 при тексте 6:30 / 5:30–5:45 / 6:30 — теперь среднее считает код."""
    zones = zones_for()
    day = pf.normalize_day(TEMPO_DAY)
    r = pf.resolve_segments(day["segments"], zones)
    assert r["distance_km"] == 6.0
    total_time = sum(s["duration_min"] for s in r["segments"])
    assert abs(r["duration_min"] - total_time) < 0.11
    assert abs(r["avg_pace"] - r["duration_min"] / r["distance_km"]) < 0.01
    tempo_seg = r["segments"][1]
    warm = r["segments"][0]
    # средний темп медленнее темпового отрезка (в него входят разминка и заминка)
    assert r["avg_pace"] > sum(tempo_seg["pace"]) / 2
    assert r["avg_pace"] < sum(warm["pace"]) / 2
    assert tempo_seg["pace"][0] < tempo_seg["pace"][1]


def test_unknown_zones_give_distance_but_no_pace_or_time():
    zones = build_zones(make_user(), [], NOW)          # ничего не известно
    r = pf.resolve_segments(pf.normalize_day(TEMPO_DAY)["segments"], zones)
    assert r["distance_km"] == 6.0
    assert r["duration_min"] is None and r["avg_pace"] is None and r["estimated"] is True
    assert all(s["pace"] is None for s in r["segments"])


def test_duration_based_run_derives_distance_when_pace_known():
    zones = zones_for(easy=6.0)
    r = pf.resolve_segments([{"kind": "run", "zone": "easy", "duration_min": 30}], zones)
    assert 4.5 < r["distance_km"] < 5.5


def test_run_walk_uses_walk_pace_and_totals_time():
    zones = zones_for(easy=8.0)
    seg = {"kind": "run_walk", "zone": "easy", "reps": 8, "run_s": 60, "walk_s": 90}
    r = pf.resolve_segments([seg], zones)
    assert r["duration_min"] == 20.0
    assert r["distance_km"] and r["distance_km"] > 1.5


def test_run_walk_without_pace_still_has_duration():
    zones = build_zones(make_user(), [], NOW)
    seg = {"kind": "run_walk", "zone": "easy", "reps": 8, "run_s": 60, "walk_s": 90}
    r = pf.resolve_segments([seg], zones)
    assert r["duration_min"] == 20.0 and r["distance_km"] is None


def test_intervals_include_recovery_in_totals():
    zones = zones_for(easy=6.5)
    day = pf.normalize_day({"workout_type": "interval", "segments": [
        {"kind": "warmup", "distance_km": 1.5},
        {"kind": "intervals", "reps": 5, "distance_m": 800,
         "recovery": {"distance_m": 400, "zone": "recovery"}},
        {"kind": "cooldown", "distance_km": 1},
    ]})
    r = pf.resolve_segments(day["segments"], zones)
    assert abs(r["distance_km"] - (1.5 + 5 * 0.8 + 5 * 0.4 + 1)) < 0.05
    ivl = r["segments"][1]
    assert ivl["pace"][1] < r["segments"][0]["pace"][0] + 5 and ivl["recovery_pace"] is not None


def test_describe_has_no_paces_and_reads_naturally():
    assert pf.describe_workout("easy", [{"kind": "run", "zone": "easy", "distance_km": 6.0}]) == "Лёгкий бег 6 км"
    text = pf.describe_workout("tempo", pf.normalize_day(TEMPO_DAY)["segments"])
    assert text == "Темповая: 1 км разминка, 4 км в темпе, 1 км заминка"
    assert ":" not in text.split(": ", 1)[1]  # в описании нет чисел темпа вида 5:30
    rw = pf.describe_workout("easy", [{"kind": "run_walk", "zone": "easy", "reps": 8, "run_s": 60, "walk_s": 90}])
    assert rw == "Лёгкий бег: 8×(бег 1 мин, ходьба 90 сек)"
    assert pf.describe_workout("rest", []) == "Отдых"


def test_build_workout_fields_and_structure():
    zones = zones_for()
    w = pf.build_workout(pf.normalize_day(TEMPO_DAY), zones, "ai")
    assert w["plan_source"] == "ai" and w["distance_km"] == 6.0
    assert w["target_pace_min_km"] == w["plan_structure"]["resolved"]["avg_pace"]
    assert w["plan_structure"]["version"] == 2 and w["plan_structure"]["comment"] == "Держи ровно."
    rest = pf.build_workout({"workout_type": "rest", "segments": [], "comment": None}, zones, "rules")
    assert rest["plan_structure"] is None and rest["distance_km"] is None


def test_refresh_structure_self_calibrates_and_skips_legacy():
    slow = zones_for(easy=8.5)
    w = pf.build_workout(pf.normalize_day(TEMPO_DAY), slow, "ai")
    fast = zones_for(easy=6.0)
    new, fields = pf.refresh_structure(w["plan_structure"], fast)
    assert fields["target_pace_min_km"] < w["target_pace_min_km"]
    assert new["segments"] == w["plan_structure"]["segments"]      # зоны те же, числа новые
    assert pf.refresh_structure({"warmup_km": 2, "main": []}, fast) is None
    assert pf.refresh_structure(None, fast) is None


def test_scale_day_reduces_distance_and_reps():
    day = pf.normalize_day({"workout_type": "interval", "segments": [
        {"kind": "warmup", "distance_km": 2},
        {"kind": "intervals", "reps": 8, "distance_m": 400},
    ]})
    small = pf.scale_day(day, 0.5)
    assert small["segments"][0]["distance_km"] == 1.0
    assert small["segments"][1]["reps"] == 4
    assert day["segments"][1]["reps"] == 8       # исходный день не изменён
