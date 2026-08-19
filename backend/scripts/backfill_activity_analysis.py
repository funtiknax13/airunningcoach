"""Досчитывает Activity.analysis для тренировок, импортированных ДО того, как
появилась эта фича (2026-08-18) — у них есть track_points, но analysis = NULL,
поэтому на странице /activities/:id/analysis не показывается разбор/нарратив.

Считает по уже сохранённому (прореженному, ~300 точек) track_points, а не по
исходному файлу — тот нигде не хранится. Для большинства тренировок этого
достаточно (шаг между точками обычно куда мельче 50 м), но у очень длинных
активностей (100+ км) прореживание может смазать детекцию отдельных интервалов —
это не баг, а неизбежное ограничение бэкафилла по уже прореженным данным.
Также нет исходного <type>/название файла — тип бег/ходьба определяется только
по каденсу/темпу (без первого, самого надёжного сигнала — файл-тега).

Запуск на сервере:
    docker compose run --rm --no-deps -T --entrypoint python backend scripts/backfill_activity_analysis.py
"""
from __future__ import annotations

import sys
from datetime import timedelta

from app.database import SessionLocal
from app.models import Activity
from app.services.activity_analysis import compute_analysis


def main() -> int:
    db = SessionLocal()
    try:
        activities = (
            db.query(Activity)
            .filter(Activity.track_points.isnot(None), Activity.analysis.is_(None))
            .all()
        )
        print(f"Найдено {len(activities)} тренировок для бэкафилла.")

        done = skipped = failed = 0
        for a in activities:
            pts = a.track_points or []
            if len(pts) < 2:
                skipped += 1
                continue
            points = [
                {
                    "lat": p["lat"], "lon": p["lon"],
                    "t": a.date + timedelta(seconds=p["t"]) if p.get("t") is not None else None,
                    "ele": p.get("ele"), "hr": p.get("hr"), "cad": p.get("cad"),
                }
                for p in pts
            ]
            try:
                a.analysis = compute_analysis(points, type_text=None)
                done += 1
            except Exception as e:
                print(f"  ✗ activity_id={a.id}: {e}")
                failed += 1
                continue

            if done % 50 == 0:
                db.commit()
                print(f"  ...{done} посчитано, коммит")

        db.commit()
        print(f"Готово: {done} посчитано, {skipped} пропущено (мало точек), {failed} ошибок.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
