"""Тестовые пользователи для локальной проверки плана (только dev-БД!).

Запуск (из каталога backend, с переменными окружения dev-БД):
    python scripts/dev_seed.py

Создаёт (пароль у всех Demo12345!):
  fresh@example.com  — новый аккаунт БЕЗ пройденного онбординга (после входа откроется онбординг)
  runner@example.com  — бегун с историей пробежек (темп ~7:30), Premium
  nodata@example.com  — бегун без данных о темпе (при генерации появится окно «Нужны данные»)
  newbie@example.com  — новичок «0 км» (стартовая программа бег/ходьба)
Повторный запуск пересоздаёт этих пользователей с нуля. Можно сидить выборочно, не трогая
остальных:  python scripts/dev_seed.py fresh   (имена: runner, nodata, newbie, fresh)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import get_password_hash  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Activity, User  # noqa: E402

PASSWORD = "Demo12345!"


def make_user(db, email, **kw):
    old = db.query(User).filter(User.email == email).first()
    if old:
        db.delete(old)
        db.commit()
    defaults = dict(is_verified=True, onboarding_completed=True, timezone="Asia/Yekaterinburg", age=35, gender="male")
    if kw.get("onboarding_completed") is False:
        defaults.pop("gender")       # у нового пользователя пол ещё не выбран (шаг 1 онбординга)
    defaults.update(kw)
    user = User(email=email, password_hash=get_password_hash(PASSWORD), name=email.split("@")[0], **defaults)
    db.add(user)
    db.commit()
    return user


def add_run(db, user, days_ago, km, pace, hr=None):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.add(Activity(
        user_id=user.id, date=when, distance_km=km, duration_min=round(km * pace, 2),
        pace_min_per_km=pace, avg_heart_rate=hr, max_heart_rate=(hr + 20) if hr else None,
        activity_type="run", source="manual",
    ))


def main():
    only = set(sys.argv[1:])
    db = SessionLocal()
    try:
        if only and only <= {"fresh"}:
            make_user(db, "fresh@example.com", onboarding_completed=False)
            db.commit()
            print("seeded: fresh@example.com / password", PASSWORD)
            return
        runner = make_user(db, "runner@example.com", fitness_level="intermediate", running_goal="10k",
                           weekly_km=20.0, training_days=4, is_premium=True,
                           premium_until=datetime.now(timezone.utc) + timedelta(days=30))
        for days_ago, km, pace in [(1, 6, 7.4), (3, 5, 7.6), (5, 8, 7.5), (8, 6, 7.3),
                                   (10, 5, 7.7), (13, 10, 7.6), (15, 5, 7.4), (18, 6, 7.5)]:
            add_run(db, runner, days_ago, km, pace, hr=150)
        make_user(db, "nodata@example.com", fitness_level="intermediate", running_goal="10k",
                  weekly_km=20.0, training_days=4)
        make_user(db, "newbie@example.com", fitness_level="beginner", running_goal="fitness",
                  weekly_km=0.0, training_days=3)
        make_user(db, "fresh@example.com", onboarding_completed=False)
        db.commit()
        print("seeded: runner@example.com, nodata@example.com, newbie@example.com / password", PASSWORD)
    finally:
        db.close()


if __name__ == "__main__":
    main()
