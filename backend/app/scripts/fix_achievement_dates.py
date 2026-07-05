# app/scripts/fix_achievement_dates.py
"""
Одноразовый фикс: пересчитывает дату "получено" (earned_at) для ВСЕХ
достижений всех пользователей — в том числе уже разблокированных.

Зачем отдельно от backfill_achievements.py: обычный пересчёт — это
односторонний храповик, он никогда не трогает уже полученные достижения.
Если backfill_achievements.py уже запускался ДО фикса даты по активности,
все достижения были помечены датой запуска скрипта ("сегодня"), а не датой
реального события — обычный повторный запуск backfill эту дату не поправит,
т.к. ключ уже числится разблокированным. Этот скрипт специально пересчитывает
дату и для уже полученных достижений.

Запуск внутри backend-контейнера:
    docker compose exec backend python -m app.scripts.fix_achievement_dates
"""
from app.database import SessionLocal
from app.models import User
from app.services.badge_achievements import recompute_and_fix_dates


def main() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        total = len(users)
        print(f"Пользователей к пересчёту дат: {total}")
        for i, user in enumerate(users, 1):
            recompute_and_fix_dates(user.id, db)
            print(f"  [{i}/{total}] {user.email}")
        print("Готово.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
