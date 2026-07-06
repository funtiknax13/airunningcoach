"""
Парсер FIT-файлов (Garmin, Coros, Suunto).

Извлекает:
- итоговые метрики из сообщения 'session'
- круги из сообщений 'lap'
- сплиты по км из записей 'record'
- прореженный GPS-трек
"""
from datetime import datetime, timezone
from typing import Optional

try:
    import fitparse
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

if _AVAILABLE:
    from fitparse.records import (
        BASE_TYPES, BASE_TYPE_BYTE, FieldDefinition, DevFieldDefinition,
        DefinitionMessage, get_dev_type,
    )
    from fitparse.profile import MESSAGE_TYPES

    def _lenient_parse_definition_message(self, header):
        """Заменяет fitparse.base.FitFile._parse_definition_message.

        Апстрим падает с FitParseError, если размер поля не кратен размеру его
        типа (встречается у некоторых устройств — сам fitparse признаёт в
        комментарии "we could fall back to byte encoding... for now, just
        throw"). Мы делаем этот фолбэк: читаем поле как сырые байты вместо
        краха всего файла — смещение остальных полей не меняется, теряется
        только типизация этого одного поля.
        """
        endian = '>' if self._read_struct('xB') else '<'
        global_mesg_num, num_fields = self._read_struct('HB', endian=endian)
        mesg_type = MESSAGE_TYPES.get(global_mesg_num)
        field_defs = []

        for _ in range(num_fields):
            field_def_num, field_size, base_type_num = self._read_struct('3B', endian=endian)
            field = mesg_type.fields.get(field_def_num) if mesg_type else None
            base_type = BASE_TYPES.get(base_type_num, BASE_TYPE_BYTE)

            if (field_size % base_type.size) != 0:
                base_type = BASE_TYPE_BYTE

            if field and field.components:
                for component in field.components:
                    if component.accumulate:
                        accumulators = self._accumulators.setdefault(global_mesg_num, {})
                        accumulators[component.def_num] = 0

            field_defs.append(FieldDefinition(
                field=field, def_num=field_def_num, base_type=base_type, size=field_size,
            ))

        dev_field_defs = []
        if header.is_developer_data:
            num_dev_fields = self._read_struct('B', endian=endian)
            for _ in range(num_dev_fields):
                field_def_num, field_size, dev_data_index = self._read_struct('3B', endian=endian)
                field = get_dev_type(dev_data_index, field_def_num)
                dev_field_defs.append(DevFieldDefinition(
                    field=field, dev_data_index=dev_data_index, def_num=field_def_num, size=field_size,
                ))

        def_mesg = DefinitionMessage(
            header=header, endian=endian, mesg_type=mesg_type, mesg_num=global_mesg_num,
            field_defs=field_defs, dev_field_defs=dev_field_defs,
        )
        self._local_mesgs[header.local_mesg_num] = def_mesg
        return def_mesg

    fitparse.base.FitFile._parse_definition_message = _lenient_parse_definition_message


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _compute_splits(records: list) -> list:
    """Вычисляет темп/пульс по километрам из записей 'record'."""
    splits = []
    km_num, km_base_dist, km_base_time = 1, 0.0, None
    km_hrs = []

    for r in records:
        dist = r.get("distance")
        ts   = r.get("timestamp")
        hr   = r.get("heart_rate")
        if dist is None: continue
        dist_km = dist / 1000

        if hr and hr > 0: km_hrs.append(hr)
        if km_base_time is None and ts: km_base_time = ts

        if dist_km - km_base_dist >= 1.0 and km_base_time and ts:
            elapsed_min = (ts - km_base_time).total_seconds() / 60
            seg_dist = dist_km - km_base_dist
            splits.append({
                "km":     km_num,
                "pace":   round(elapsed_min / seg_dist, 2) if seg_dist > 0 else None,
                "avg_hr": round(sum(km_hrs)/len(km_hrs)) if km_hrs else None,
            })
            km_num    += 1
            km_base_dist = dist_km
            km_base_time = ts
            km_hrs = []

    return splits


def _downsample(records: list, max_pts: int = 300, interval_sec: int = 10) -> list:
    if not records: return []
    result = [records[0]]
    last_t = records[0].get("timestamp")
    for r in records[1:]:
        t = r.get("timestamp")
        if t and last_t and (t - last_t).total_seconds() >= interval_sec:
            result.append(r); last_t = t
        if len(result) >= max_pts: break
    return result


def parse_fit(content: bytes) -> dict:
    if not _AVAILABLE:
        raise ValueError("Библиотека fitparse не установлена. Используйте GPX-формат.")

    try:
        ff = fitparse.FitFile(content)

        # ── Читаем все сообщения ────────────────────────────────────────────
        session_data = {}
        lap_msgs     = []
        records      = []

        for msg in ff.get_messages():
            name = msg.name
            data = {f.name: f.value for f in msg if f.value is not None}

            if name == "session":
                session_data = data
            elif name == "lap":
                lap_msgs.append(data)
            elif name == "record":
                records.append(data)
    except fitparse.utils.FitParseError:
        raise ValueError("Не удалось прочитать FIT-файл — он повреждён или экспортирован в нестандартном формате. Попробуйте экспортировать тренировку в GPX.")

    # ── Тип активности из session.sport ─────────────────────────────────────
    _FIT_SPORT_MAP = {
        "running":   "run",
        "cycling":   "ride",
        "walking":   "walk",
        "hiking":    "hike",
        "swimming":  "swim",
        "training":  "strength",
        "fitness_equipment": "workout",
        "cardio":    "workout",
    }
    raw_sport = str(session_data.get("sport", "")).lower()
    activity_type = _FIT_SPORT_MAP.get(raw_sport, "run" if not raw_sport else "other")

    # ── Основные метрики из session ──────────────────────────────────────────
    distance_km  = (session_data.get("total_distance") or 0) / 1000
    duration_min = (session_data.get("total_timer_time") or 0) / 60
    avg_hr       = session_data.get("avg_heart_rate")
    max_hr       = session_data.get("max_heart_rate")
    avg_cad      = session_data.get("avg_running_cadence")
    if avg_cad: avg_cad = int(avg_cad * 2)   # одна нога → обе
    elevation_gain = session_data.get("total_ascent")
    start_time   = _to_utc(session_data.get("start_time"))
    calories     = session_data.get("total_calories")

    # Фолбэк на records если session пустой
    if distance_km < 0.01 and records:
        dists = [r["distance"] for r in records if r.get("distance")]
        times = [r["timestamp"] for r in records if r.get("timestamp")]
        if dists: distance_km = max(dists) / 1000
        if len(times) >= 2:
            duration_min = (times[-1] - times[0]).total_seconds() / 60
        hr_vals = [r["heart_rate"] for r in records if r.get("heart_rate")]
        if hr_vals:
            avg_hr = round(sum(hr_vals) / len(hr_vals))
            max_hr = max(hr_vals)

    if distance_km < 0.1:
        raise ValueError("Дистанция слишком маленькая (< 100 м).")
    if duration_min <= 0:
        raise ValueError("Длительность тренировки равна нулю.")

    if not start_time:
        times = [r["timestamp"] for r in records if r.get("timestamp")]
        start_time = _to_utc(times[0]) if times else datetime.now(timezone.utc)

    # ── Круги (laps) ─────────────────────────────────────────────────────────
    laps = []
    for i, lap in enumerate(lap_msgs):
        dist = (lap.get("total_distance") or 0) / 1000
        dur  = (lap.get("total_timer_time") or 0) / 60
        laps.append({
            "num":     i + 1,
            "dist_km": round(dist, 3),
            "dur_min": round(dur, 2),
            "pace":    round(dur / dist, 2) if dist > 0 else None,
            "avg_hr":  lap.get("avg_heart_rate"),
            "max_hr":  lap.get("max_heart_rate"),
        })

    # ── Сплиты по км ─────────────────────────────────────────────────────────
    splits = _compute_splits(records) if records else []

    # ── Прореженный трек ─────────────────────────────────────────────────────
    has_gps = any(r.get("position_lat") for r in records)
    track_points = []
    if has_gps:
        sampled = _downsample(records)
        t0 = start_time
        for r in sampled:
            lat = r.get("position_lat")
            lon = r.get("position_lon")
            if lat is None or lon is None: continue
            # FIT хранит координаты в semicircles → градусы
            lat_deg = lat * (180 / 2**31)
            lon_deg = lon * (180 / 2**31)
            ts  = _to_utc(r.get("timestamp"))
            pt = {
                "t":    int((ts - t0).total_seconds()) if ts else None,
                "lat":  round(lat_deg, 6),
                "lon":  round(lon_deg, 6),
                "dist": round((r.get("distance") or 0) / 1000, 3),
            }
            if r.get("altitude"):    pt["ele"] = round(r["altitude"], 1)
            if r.get("heart_rate"):  pt["hr"]  = r["heart_rate"]
            track_points.append(pt)

    return {
        "date":           start_time,
        "distance_km":    round(distance_km, 3),
        "duration_min":   round(duration_min, 2),
        "avg_heart_rate": int(avg_hr) if avg_hr else None,
        "max_heart_rate": int(max_hr) if max_hr else None,
        "avg_cadence":    int(avg_cad) if avg_cad else None,
        "elevation_gain": round(float(elevation_gain), 1) if elevation_gain else None,
        "calories":       int(calories) if calories else None,
        "laps":           laps if len(laps) > 1 else None,
        "splits":         splits if splits else None,
        "track_points":   track_points if track_points else None,
        "activity_type":  activity_type,
        "source":         "fit",
    }
