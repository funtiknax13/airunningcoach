from app.services import zones as z
from tests.conftest import make_run, make_user, NOW


def test_fmt_pace():
    assert z.fmt_pace(6.5) == "6:30"
    assert z.fmt_pace(5.4) == "5:24"
    assert z.fmt_pace(None) == "—"


def test_easy_pace_from_result_5k():
    # 5 км за 25:00 -> темп 5:00 -> лёгкий ≈ 6:30
    assert z.easy_pace_from_result(5, 25) == 6.5


def test_easy_pace_from_result_rejects_garbage():
    assert z.easy_pace_from_result(0, 25) is None
    assert z.easy_pace_from_result(5, 0) is None
    assert z.easy_pace_from_result(0.3, 2) is None
    assert z.easy_pace_from_result(5, 5) is None  # 1:00/км — нереально


def test_riegel_longer_is_slower_per_km():
    t10 = z.riegel_time(5, 25, 10)
    assert t10 > 50  # 10 км дольше двух пятёрок из-за показателя 1.06


def test_no_data_means_unknown_zones():
    zones = z.build_zones(make_user(), [], NOW)
    assert zones.easy_pace is None
    assert zones.pace_confidence == "none"
    assert all(v is None for v in zones.pace.values())
    assert z.data_status(zones, [], NOW)["needs_data"] is True


def test_profile_easy_pace_orders_zones_and_is_sane():
    zones = z.build_zones(make_user(easy_pace_min_km=7 + 50 / 60), [], NOW)
    assert zones.pace_source == "profile" and zones.pace_confidence == "medium"
    mids = {k: zones.pace_mid(k) for k in z.ZONE_KEYS}
    # чем интенсивнее зона, тем меньше минут на км
    assert mids["interval"] < mids["tempo"] < mids["easy"] < mids["long"] < mids["recovery"]
    for lo, hi in zones.pace.values():
        assert lo < hi  # быстрая граница строго быстрее медленной
    # для лёгкого 7:50 темповый заметно медленнее "5:30" из багрепорта
    assert zones.pace["tempo"][0] > 6.0


def test_result_beats_history_and_profile():
    runs = [make_run(3, 5, 8.0) for _ in range(4)]
    user = make_user(race_distance_km=5, race_time_min=25, easy_pace_min_km=9.0)
    zones = z.build_zones(user, runs, NOW)
    assert zones.pace_source == "result" and zones.pace_confidence == "high"
    assert zones.easy_pace == 6.5


def test_history_median_medium_with_three_runs():
    runs = [make_run(2, 5, 7.4), make_run(5, 6, 7.6), make_run(9, 4, 7.5)]
    zones = z.build_zones(make_user(), runs, NOW)
    assert zones.pace_source == "history" and zones.pace_confidence == "medium"
    assert abs(zones.easy_pace - 7.5) < 1e-9


def test_history_low_with_single_run_but_profile_wins_over_low():
    runs = [make_run(2, 5, 7.4)]
    assert z.build_zones(make_user(), runs, NOW).pace_confidence == "low"
    zones = z.build_zones(make_user(easy_pace_min_km=8.0), runs, NOW)
    assert zones.pace_source == "profile"


def test_old_and_non_run_activities_ignored():
    runs = [make_run(90, 5, 6.0), make_run(3, 5, 6.0, activity_type="ride"),
            make_run(3, 0.5, 6.0), make_run(3, 5, 25.0)]
    zones = z.build_zones(make_user(), runs, NOW)
    assert zones.pace_source == "none"


def test_hard_effort_run_acts_like_a_result():
    runs = [make_run(2, 5, 6.0, effort="hard")]  # 5 км за 30:00
    zones = z.build_zones(make_user(), runs, NOW)
    assert zones.pace_source == "history_effort" and zones.pace_confidence == "high"
    assert abs(zones.easy_pace - 7.8) < 0.01


def test_short_hard_effort_is_only_medium():
    runs = [make_run(2, 2, 6.0, effort="hard")]
    assert z.build_zones(make_user(), runs, NOW).pace_confidence == "medium"


def test_easy_flagged_run_is_medium_even_alone():
    runs = [make_run(2, 5, 7.0, effort="easy")]
    zones = z.build_zones(make_user(), runs, NOW)
    assert zones.pace_confidence == "medium" and zones.easy_pace == 7.0


def test_hr_karvonen_when_rest_known():
    zones = z.build_zones(make_user(max_hr=190, rest_hr=60), [], NOW)
    assert zones.hr_method == "karvonen" and zones.hr_confidence == "high"
    assert zones.hr["tempo"] == (164, 174)
    assert zones.hr["easy"] == (138, 151)


def test_hr_percent_of_max_without_rest():
    zones = z.build_zones(make_user(max_hr=190), [], NOW)
    assert zones.hr_method == "max"
    assert zones.hr["tempo"] == (156, 169)


def test_hr_fallbacks_history_then_age_then_none():
    from_hist = z.build_zones(make_user(age=30), [make_run(3, 5, 7.0, max_hr=185)], NOW)
    assert from_hist.hr_source == "history" and from_hist.max_hr == 185
    from_age = z.build_zones(make_user(age=30), [], NOW)
    assert from_age.hr_source == "age" and from_age.max_hr == 187 and from_age.hr_confidence == "low"
    none = z.build_zones(make_user(age=None), [], NOW)
    assert none.hr_method == "none" and none.hr["tempo"] is None


def test_invalid_profile_hr_ignored():
    zones = z.build_zones(make_user(max_hr=300, rest_hr=5, age=40), [], NOW)
    assert zones.hr_source == "age" and zones.rest_hr is None


def test_rest_hr_ignored_if_close_to_max():
    zones = z.build_zones(make_user(max_hr=150, rest_hr=140), [], NOW)
    assert zones.hr_method == "max"


def test_data_status_counts_recent_runs():
    runs = [make_run(3, 5, 7.0), make_run(10, 5, 7.0), make_run(60, 5, 7.0)]
    zones = z.build_zones(make_user(), runs, NOW)
    st = z.data_status(zones, runs, NOW)
    assert st["recent_runs"] == 2 and st["last_run_days_ago"] == 3
    assert st["needs_data"] is True   # 2 пробежки = low

def test_to_dict_is_json_friendly():
    import json
    zones = z.build_zones(make_user(easy_pace_min_km=7.0, max_hr=190), [], NOW)
    json.dumps(zones.to_dict())
