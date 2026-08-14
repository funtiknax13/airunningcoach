"""Смоук-тест доступности Groq (в т.ч. через прокси).

Запуск на сервере:
    docker compose run --rm --no-deps -T --entrypoint python backend scripts/check_groq_proxy.py

Что показывает:
  • задан ли GROQ_PROXY и какой ключ (маскированно);
  • результат крошечного chat-запроса к Groq;
  • если прилетает 403 — это гео/аккаунтный блок; сравни с/без прокси, чтобы понять какой.
"""
from __future__ import annotations

import sys

from app.core.config import settings
from app.services.ai_agent import _client_for


def _mask(s: str) -> str:
    if not s:
        return "(пусто)"
    return f"{s[:4]}…{s[-4:]} (len={len(s)})" if len(s) > 10 else "(задан)"


def main() -> int:
    print("GROQ_API_KEY :", _mask(settings.GROQ_API_KEY))
    print("GROQ_BASE_URL:", settings.GROQ_BASE_URL)
    print("GROQ_MODEL   :", settings.GROQ_MODEL)
    print("GROQ_PROXY   :", settings.GROQ_PROXY or "(нет — идём напрямую)")

    if not settings.GROQ_API_KEY:
        print("\n✗ GROQ_API_KEY не задан — включать нечего.")
        return 2

    prov = {"name": "groq", "base_url": settings.GROQ_BASE_URL,
            "api_key": settings.GROQ_API_KEY, "model": settings.GROQ_MODEL,
            "proxy": settings.GROQ_PROXY or None}
    client = _client_for(prov)

    print("\n→ Пробный запрос к Groq…")
    try:
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5, temperature=0,
        )
        print("✓ OK. Ответ:", (resp.choices[0].message.content or "").strip()[:60])
        print("  Прокси РАБОТАЕТ (или Groq доступен напрямую)." if settings.GROQ_PROXY
              else "  Groq доступен напрямую — прокси не требуется.")
        return 0
    except Exception as e:
        code = getattr(e, "status_code", None)
        print(f"✗ Ошибка ({type(e).__name__}, status={code}): {e}")
        if code == 403:
            print("  403 = блок. Если это БЕЗ прокси — вероятно гео (пробуй прокси).")
            print("  Если 403 остаётся ЧЕРЕЗ рабочий прокси в разрешённой стране — блок аккаунтный.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
