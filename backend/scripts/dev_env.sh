#!/bin/bash
# Изолированное DEV-окружение для локальной проверки плана (Git Bash: `source scripts/dev_env.sh`).
#
# Что делает: указывает на локальную БД (Docker, порт 5544) и ОБНУЛЯЕТ все внешние
# ключи (ИИ, почта, платежи, OAuth), перебивая значения из backend/.env — переменные
# окружения приоритетнее файла. Так локальный запуск не тратит боевые ключи и не шлёт письма.
#
# Почему Git Bash, а не PowerShell: в PowerShell присвоение пустой строки ($env:X="")
# УДАЛЯЕТ переменную, и значение из .env «просочится» обратно.
#
# Ключи ИИ для проверки НЕ записывайте в файлы репозитория — задайте их вручную в этой же
# сессии терминала после source:
#     export GROQ_API_KEY="..."        # и/или
#     export DEEPSEEK_API_KEY="..."
export SECRET_KEY="local-dev-secret-not-for-prod-0123456789abcdef"
export DATABASE_URL="postgresql://postgres:dev@localhost:5544/dev"
export GROQ_API_KEY="" DEEPSEEK_API_KEY="" GROQ_PROXY=""
export GMAIL_USER="" GMAIL_APP_PASSWORD=""
export YOOKASSA_SHOP_ID="" YOOKASSA_SECRET_KEY=""
export GOOGLE_CLIENT_ID="" GOOGLE_CLIENT_SECRET=""
export ORS_API_KEY="" ALTCHA_HMAC_KEY="" GEMINI_API_KEY=""
export CUSTOM_AI_API_KEY="" CUSTOM_AI_BASE_URL="" CUSTOM_AI_MODEL=""
export VAPID_PUBLIC_KEY="" VAPID_PRIVATE_KEY=""
export APP_BASE_URL="http://localhost:5173"
echo "DEV-окружение: БД localhost:5544/dev, внешние ключи обнулены."
# локальные секреты (если файл есть) — после обнуления, чтобы они его перебили
[ -f "$(dirname "${BASH_SOURCE[0]}")/dev_env.local.sh" ] && source "$(dirname "${BASH_SOURCE[0]}")/dev_env.local.sh" && echo "Подхвачены локальные dev-секреты."
