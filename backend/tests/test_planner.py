from collections import defaultdict
from datetime import date, datetime, timedelta

import pytest

from app.services import plan_format as pf
from app.services import planner as pl
from app.services.zones import build_zones
from tests.conftest import make_user, make_run, NOW

START = datetime(2026, 9, 24)   # четверг
MONDAY = datetime(2026, 9, 28)


def req_for(**kw):
    user = kw.pop("user", None) or make_user(easy_pace_min_km=7.0)
    zones = kw.pop("zones", None) or build_zones(user, [], NOW)
    base = dict(start=START, days=28, zones=zones, training_days=4, level="intermediate",
                goal="10k", weekly_km_profile=20.0)
    base.update(kw)
    return pl.PlanRequest(**base)


def weeks_of(days, start=START):
    out = defaultdict(list)
    for i, d in enumerate(days):
        dt = (start + timedelta(days=i)).date()
        out[dt - timedelta(days=dt.weekday())].append((dt.weekday(), d))
    return out


def active(day_list):
    return [(wd, d) for wd, d in day_list if d["workout_type"] != "rest"]


def test_choose_weekdays_tables_and_shift():
    assert pl.choose_weekdays(4, 6) == [0, 2, 4, 6]
    assert pl.choose_weekdays(3, 5) == [0, 2, 5]            # длинная в субботу: сдвиг на -1
    assert pl.choose_weekdays(9, 6) == [0, 1, 3, 4, 5, 6]   # не больше 6


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_exact_training_days_per_full_week(n):
    days, meta = pl.generate_plan(req_for(training_days=n, start=MONDAY))
    assert len(days) == 28
    for wk in weeks_of(days, MONDAY).values():
        assert len(active(wk)) == n


def test_long_run_on_requested_day_and_within_cap():
    r = req_for(long_run_day=5, longest_run_km=10.0, weekly_km_profile=30.0)
    days, _ = pl.generate_plan(r)
    for w, (monday, wk) in enumerate(weeks_of(days).items()):
        for wd, d in wk:
            if d["workout_type"] == "long":
                assert wd == 5
                assert pf.day_distance_km(d, r.zones) <= pl.long_cap_km(r, w) + 0.01


def test_weekly_volume_progression_deload_and_cap():
    r = req_for(weekly_km_profile=20.0, start=MONDAY, longest_run_km=12.0)
    days, _ = pl.generate_plan(r)
    mondays = list(weeks_of(days, r.start))
    totals = [sum(pf.day_distance_km(d, r.zones) for _, d in wk) for wk in weeks_of(days, r.start).values()]
    assert totals[3] < totals[2]                      # 4-я неделя легче (разгрузка)
    assert totals[1] >= totals[0] * 0.9               # без падения в развивающих неделях
    for i, t in enumerate(totals):
        assert t <= pl.week_target_km(r, i, mondays[i]) * 1.25


def test_quality_workouts_appear_only_with_known_zones():
    with_zones = pl.generate_plan(req_for(start=MONDAY))[0]
    assert {d["workout_type"] for d in with_zones} & {"tempo", "interval"}
    none_zones = build_zones(make_user(), [], NOW)
    days = pl.generate_plan(req_for(zones=none_zones, start=MONDAY))[0]
    assert not {d["workout_type"] for d in days} & {"tempo", "interval"}


def test_low_confidence_defers_quality_two_weeks():
    z = build_zones(make_user(), [make_run(2, 5, 7.5)], NOW)        # 1 пробежка = low
    assert z.pace_confidence == "low"
    days = pl.generate_plan(req_for(zones=z, start=MONDAY))[0]
    assert not {d["workout_type"] for d in days[:14]} & {"tempo", "interval"}


def test_fitness_goal_and_deload_have_no_quality():
    days = pl.generate_plan(req_for(goal="fitness", start=MONDAY))[0]
    assert not {d["workout_type"] for d in days} & {"tempo", "interval"}
    days = pl.generate_plan(req_for(start=MONDAY))[0]
    assert not {d["workout_type"] for d in days[21:28]} & {"tempo", "interval"}   # 4-я неделя


def test_beginner_mode_uses_time_based_run_walk_and_caps_days():
    r = req_for(level="beginner", weekly_km_profile=0.0, training_days=5,
                zones=build_zones(make_user(), [], NOW), start=MONDAY)
    assert pl.is_beginner_mode(r)
    days, meta = pl.generate_plan(r)
    assert meta["mode"] == "beginner" and meta["training_days"] == 4 and meta["training_days_requested"] == 5
    first = next(d for d in days if d["workout_type"] != "rest")
    assert [s["kind"] for s in first["segments"]] == ["walk", "run_walk", "walk"]
    assert first["segments"][1]["run_s"] == 60
    resolved = pf.resolve_segments(first["segments"], r.zones)
    assert resolved["duration_min"] and resolved["distance_km"] is None     # без зон: только время
    weeks = list(weeks_of(days, r.start).values())
    assert first["segments"][1] != next(d for _, d in active(weeks[1]))["segments"][1]


def test_beginner_progress_continues_from_completed_sessions():
    base = dict(level="beginner", weekly_km_profile=0.0, training_days=3,
                zones=build_zones(make_user(), [], NOW), start=MONDAY, days=7)
    fresh = pl.generate_plan(req_for(**base))[0]
    later = pl.generate_plan(req_for(completed_beginner_sessions=6, **base))[0]
    a = next(d for d in fresh if d["workout_type"] != "rest")["segments"][1]
    b = next(d for d in later if d["workout_type"] != "rest")["segments"][1]
    assert a["run_s"] == 60 and b["run_s"] == 180          # неделя 3 программы


def test_hard_rpe_repeats_previous_beginner_week():
    base = dict(level="beginner", weekly_km_profile=0.0, training_days=3,
                zones=build_zones(make_user(), [], NOW), start=MONDAY, days=7,
                completed_beginner_sessions=6)
    ok_week = pl.generate_plan(req_for(recent_rpe=["ok"], **base))[0]
    hard_week = pl.generate_plan(req_for(recent_rpe=["hard"], **base))[0]
    e = next(d for d in ok_week if d["workout_type"] != "rest")["segments"][1]
    h = next(d for d in hard_week if d["workout_type"] != "rest")["segments"][1]
    assert h["run_s"] < e["run_s"]


def test_history_baseline_beats_profile_and_cold_start_is_conservative():
    runs = [make_run(d, 5, 7.0) for d in (2, 6, 9, 13, 16, 20)]
    stats = pl.history_stats(runs, NOW)
    assert stats["runs_4w"] == 6 and stats["avg_km"] == pytest.approx(10.0)   # 30 км за ~3 недели
    r = req_for(history_avg_km=stats["avg_km"], history_runs_4w=6, weekly_km_profile=40.0)
    assert pl.baseline_km(r) == 10.0                   # человек завысил, история честнее
    cold = req_for(weekly_km_profile=None, level="advanced")
    assert pl.baseline_km(cold) == pl.LEVEL_DEFAULT_KM["advanced"]


def test_taper_before_goal_date_reduces_volume():
    plain = req_for(start=MONDAY)
    taper = req_for(start=MONDAY, goal_date=date(2026, 10, 12))
    assert pl.week_target_km(taper, 2, date(2026, 10, 12)) < pl.week_target_km(plain, 2, date(2026, 10, 12))
    assert pl.week_target_km(taper, 1, date(2026, 10, 5)) == pytest.approx(
        pl.week_target_km(plain, 1, date(2026, 10, 5)) * 0.75)


def test_generated_plan_is_valid_format_and_resolves():
    r = req_for(start=MONDAY)
    days, _ = pl.generate_plan(r)
    for d in days:
        pf.build_workout(pf.normalize_day(d), r.zones, "rules")     # валидно и считается


def test_cap_training_days_on_raw_and_canonical():
    raw = [{"workout_type": t, "distance_km": 5 + i} for i, t in
           enumerate(["easy", "tempo", "easy", "interval", "recovery", "long", "easy"])]
    out = pl.cap_training_days(raw, MONDAY, 4)
    assert sum(d["workout_type"] != "rest" for d in out) == 4
    assert {"long", "tempo", "interval"} <= {d["workout_type"] for d in out}    # ценное сохранено
    assert pl.cap_training_days(raw, MONDAY, None) is raw


def test_enforce_envelope_scales_overloaded_ai_plan_and_caps_long():
    r = req_for(start=MONDAY, weekly_km_profile=20.0, longest_run_km=8.0, days=7, training_days=4)
    rest = {"workout_type": "rest", "segments": [], "comment": None}
    run = lambda t, z, km: {"workout_type": t, "comment": None,
                            "segments": [{"kind": "run", "zone": z, "distance_km": km}]}
    ai = [run("long", "long", 25), rest, run("easy", "easy", 15), rest, run("easy", "easy", 15), rest, rest]
    out = pl.enforce_envelope(ai, r)
    assert pf.day_distance_km(out[0], r.zones) <= pl.long_cap_km(r, 0) + 0.5
    total = sum(pf.day_distance_km(d, r.zones) for d in out)
    assert total <= pl.week_target_km(r, 0, date(2026, 9, 28)) * pl.WEEK_CAP_TOLERANCE + 1.5


def test_constraints_shape():
    c = pl.compute_constraints(req_for(start=MONDAY))
    assert c["training_days"] == 4 and len(c["weeks"]) == 4
    assert c["weeks"][3]["deload"] is True and c["weeks"][3]["cap_km"] < c["weeks"][2]["cap_km"]


def test_small_volume_falls_back_from_interval_to_tempo_not_to_easy():
    # ~13 км/нед: интервалы (нужно >= ~5.6 км сессии) не помещаются, темповая — помещается
    r = req_for(start=MONDAY, weekly_km_profile=13.0, history_avg_km=None, goal="10k")
    days, _ = pl.generate_plan(r)
    week1 = days[7:14]                                   # w=1 -> для 10k «интервальная» неделя
    kinds = {d["workout_type"] for d in week1}
    assert "interval" not in kinds and "tempo" in kinds


def test_history_average_uses_active_span_not_fixed_four_weeks():
    # все пробежки за последние 18 дней (~3 недели): среднее — по 3 неделям, а не по 4
    runs = [make_run(d, km, 7.5) for d, km in [(1, 6), (3, 5), (5, 8), (8, 6), (10, 5), (13, 10), (15, 5), (18, 6)]]
    stats = pl.history_stats(runs, NOW)
    assert stats["avg_km"] == pytest.approx(51 / 3)
    assert stats["longest_km"] == 10


def test_long_run_does_not_regress_below_share_of_recent_longest():
    """Регрессия: бегун с 10 км за плечами получал длинную 4.5 км."""
    r = req_for(start=MONDAY, history_avg_km=17.0, history_runs_4w=8, longest_run_km=10.0,
                weekly_km_profile=20.0)
    days, _ = pl.generate_plan(r)
    longs = [pf.day_distance_km(d, r.zones) for d in days if d["workout_type"] == "long"]
    assert longs and min(longs[:2]) >= 7.0            # >= 70% от 10 км
    assert max(longs) <= pl.long_cap_km(r, 3) + 0.5


def test_long_floor_never_exceeds_cap_and_week_volume_still_reasonable():
    r = req_for(start=MONDAY, history_avg_km=8.0, history_runs_4w=6, longest_run_km=12.0)
    days, _ = pl.generate_plan(r)
    week0 = [d for d in days[:7]]
    total = sum(pf.day_distance_km(d, r.zones) for d in week0)
    long_km = max(pf.day_distance_km(d, r.zones) for d in week0)
    assert long_km <= pl.long_cap_km(r, 0) + 0.5
    assert total <= pl.week_target_km(r, 0, MONDAY.date()) * 1.6      # не раздуваем неделю ради длинной


def test_deload_week_lowers_the_long_run_too():
    r = req_for(start=MONDAY, history_avg_km=17.0, history_runs_4w=8, longest_run_km=10.0)
    days, _ = pl.generate_plan(r)
    long_by_week = [max(pf.day_distance_km(d, r.zones) for d in days[i:i + 7]) for i in (0, 7, 14, 21)]
    assert long_by_week[3] < long_by_week[2]


def test_small_volume_gets_short_400m_intervals():
    r = req_for(start=MONDAY, weekly_km_profile=18.0, goal="5k")
    days, _ = pl.generate_plan(r)
    interval_days = [d for d in days if d["workout_type"] == "interval"]
    assert interval_days, "при ~18 км/нед интервалы теперь помещаются (короткие повторы)"
    seg = next(s for s in interval_days[0]["segments"] if s["kind"] == "intervals")
    assert seg["distance_m"] in (400, 800) and 3 <= seg["reps"] <= 10 and seg["recovery"]["distance_m"] * 2 == seg["distance_m"]


def test_interval_helper_returns_none_when_too_small_and_quality_types():
    assert pl._interval(3.0) is None
    r = req_for(goal="10k")
    assert pl.quality_types(r, 1, 1) == ["interval"] and pl.quality_types(r, 0, 1) == ["tempo"]
    assert pl.quality_types(r, 0, 2) == ["tempo", "interval"] and pl.quality_types(r, 0, 0) == []


def test_enforce_envelope_raises_undersized_long_to_floor():
    r = req_for(start=MONDAY, history_avg_km=17.0, history_runs_4w=8, longest_run_km=10.0, days=7)
    rest = {"workout_type": "rest", "segments": [], "comment": None}
    run = lambda t, z, km: {"workout_type": t, "comment": None,
                            "segments": [{"kind": "run", "zone": z, "distance_km": km}]}
    ai = [run("easy", "easy", 3), rest, run("easy", "easy", 3), rest, run("easy", "easy", 3), rest, run("long", "long", 4.5)]
    out = pl.enforce_envelope(ai, r)
    floor = pl.long_floor_km(r, 0, pl.week_target_km(r, 0, MONDAY.date()))
    assert floor >= 6.5
    assert pf.day_distance_km(out[6], r.zones) >= floor * 0.95
