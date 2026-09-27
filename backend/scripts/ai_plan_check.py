"""Проверка ИИ-генерации плана на РЕАЛЬНЫХ провайдерах (только dev-БД и dev-ключи!).

Делает минимум запросов: по одной недельной генерации на пользователя (+ один ответ
чата с флагом --chat). Ничего не пишет в БД (план не сохраняется) — только печатает.

Запуск из каталога backend, когда в окружении заданы DATABASE_URL dev-БД и ключи
GROQ_API_KEY / DEEPSEEK_API_KEY (см. LOCAL_PLAN_CHECK.md):
    python scripts/ai_plan_check.py                 # runner + nodata
    python scripts/ai_plan_check.py --chat          # + один ответ тренера
    python scripts/ai_plan_check.py runner@example.com
Ожидаемо при рабочем ИИ: source=ai, reason=None. source=rules — ИИ не справился
(смотрите reason и логи), это штатный откат на алгоритм.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services import ai_agent  # noqa: E402


async def check(email: str, chat: bool) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"{email}: пользователя нет (запустите scripts/dev_seed.py)")
            return
        start = ai_agent._plan_start(user)
        history = ai_agent.load_chat_history(db, user.id)
        outcome = await ai_agent.generate_plan_outcome(user, db, history, 7, start)
        active = [w for w in outcome.workouts if w["workout_type"] != "rest"]
        total = sum(w["distance_km"] or 0 for w in active)
        print(f"\n== {email}: source={outcome.source} reason={outcome.reason} "
              f"дней с нагрузкой={len(active)} (в профиле {user.training_days}) объём≈{total:.1f} км")
        for w in outcome.workouts:
            if w["workout_type"] == "rest":
                continue
            pace = w["target_pace_min_km"]
            comment = (w["plan_structure"] or {}).get("comment")
            print(f"  {w['workout_type']:8} {w['description']}  | ср.темп={pace}  | {comment}")
        if chat:
            db2 = SessionLocal()
            try:
                user2 = db2.query(User).filter(User.email == email).first()
                reply = await ai_agent.chat_response("Какой у меня темп для темповой и какой пульс?", user2, db2, [], "ru")
                print("  чат:", reply)
            finally:
                db2.close()
    finally:
        db.close()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    emails = args or ["runner@example.com", "nodata@example.com"]
    if ai_agent._STUB_MODE:
        print("Ключи ИИ не заданы — будет использован алгоритм (source=rules, reason=no_ai).")
    for email in emails:
        asyncio.run(check(email, "--chat" in sys.argv))


if __name__ == "__main__":
    main()
