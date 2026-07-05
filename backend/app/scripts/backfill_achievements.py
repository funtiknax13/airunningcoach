# app/scripts/backfill_achievements.py
"""
Одноразовый бэкафилл: пересчитывает личные рекорды и достижения для ВСЕХ
существующих пользователей.

Зачем: recompute_achievements() вызывается только при создании/изменении
Activity — пользователи, не логировавшие новых пробежек после появления или
последнего расширения системы достижений (10 -> 30 бейджей), не получили
пересчёта и не видят то, что уже фактически заслужили по старой истории.

Запуск внутри backend-контейнера:
    docker compose exec backend python -m app.scripts.backfill_achievements
"""
from app.database import SessionLocal
from app.models import User
from app.services.achievements import recompute_achievements


def main() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        total = len(users)
        print(f"Пользователей к пересчёту: {total}")
        for i, user in enumerate(users, 1):
            recompute_achievements(user.id, db)
            print(f"  [{i}/{total}] {user.email}")
        print("Готово.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
