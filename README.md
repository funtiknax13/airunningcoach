# AIRunningCoach

Персональный AI-тренер по бегу. Анализирует тренировки, ставит цели, генерирует недельные планы и отвечает на вопросы через встроенный чат-бот.

## Стек

| Слой | Технологии |
|------|-----------|
| Фронтенд | Vue 3 + TypeScript + Vite + Pinia |
| Бэкенд | FastAPI + SQLAlchemy + Alembic |
| База данных | PostgreSQL 16 |
| AI | DeepSeek API |
| Прокси | Nginx |
| Деплой | Docker Compose |

---

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd runapp
```

### 2. Создать `.env`

Скопировать шаблон и заполнить значения:

```bash
cp .env.example .env
```

Обязательные поля в `.env`:

```env
POSTGRES_PASSWORD=придумай_сложный_пароль
DATABASE_URL=postgresql://runcoach:придумай_сложный_пароль@postgres:5432/runcoach
SECRET_KEY=сгенерируй_случайный_ключ   # python -c "import secrets; print(secrets.token_hex(32))"
DEEPSEEK_API_KEY=sk-...                 # platform.deepseek.com
APP_BASE_URL=http://localhost           # или https://yourdomain.com на сервере
```

Опциональные (для email и Google OAuth):

```env
# Gmail SMTP — для писем подтверждения и сброса пароля
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx  # Google Account → Security → App Passwords

# Google OAuth — вход через Google
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

### 3. Собрать фронтенд

```bash
cd frontend-v2
npm install
npm run build
cd ..
```

Билд попадёт в папку `frontend-v2-dist/`, которую nginx раздаёт как статику.

### 4. Запустить Docker

```bash
docker compose up -d --build
```

Откроется на `http://localhost` (или на порту из `NGINX_PORT`).

---

## Команды Docker

### Запуск

```bash
# Первый запуск / после изменений в коде
docker compose up -d --build

# Просто запустить (без пересборки)
docker compose up -d
```

### Остановка

```bash
# Остановить контейнеры (данные сохранятся)
docker compose down

# Остановить и удалить тома с БД (данные удалятся!)
docker compose down -v
```

### Обновление после изменений

```bash
# Изменился только бэкенд (Python-код)
docker compose build backend
docker compose up -d backend

# Изменился фронтенд (Vue/TS)
cd frontend-v2 && npm run build && cd ..
docker compose up -d nginx   # nginx подхватит новые файлы из frontend-v2-dist/

# Изменились и бэкенд, и фронтенд
cd frontend-v2 && npm run build && cd ..
docker compose up -d --build
```

### Логи

```bash
# Все контейнеры
docker compose logs -f

# Только бэкенд
docker compose logs -f backend

# Только nginx
docker compose logs -f nginx

# Последние N строк
docker compose logs backend --tail=50
```

### Состояние контейнеров

```bash
docker compose ps
```

### Пересоздать БД с нуля

```bash
# ⚠️ Удалит все данные!
docker compose down -v
docker compose up -d --build
```

---

## Локальная разработка (без Docker)

### Бэкенд

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt

# Создать .env в папке backend (или использовать корневой)
# DATABASE_URL можно оставить sqlite:///./running_coach.db для локалки

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Фронтенд

```bash
cd frontend-v2
npm install
npm run dev   # запустится на http://localhost:5173 с прокси на :8000
```

---

## Настройка Google OAuth

1. Зайти на [console.cloud.google.com](https://console.cloud.google.com/)
2. **APIs & Services → OAuth consent screen** — заполнить название приложения
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Тип: **Web application**
   - Authorized redirect URIs:
     - `http://localhost/auth/google/callback` (локально)
     - `https://yourdomain.com/auth/google/callback` (продакшн)
4. Скопировать **Client ID** и **Client Secret** в `.env`

---

## Структура проекта

```
runapp/
├── backend/                # FastAPI приложение
│   ├── app/
│   │   ├── routers/        # Эндпоинты (auth, activities, goals, training, chat, ai_insights)
│   │   ├── services/       # AI агент, email, кеш инсайтов
│   │   ├── models.py       # SQLAlchemy модели
│   │   ├── schemas.py      # Pydantic схемы
│   │   └── core/config.py  # Настройки из .env
│   ├── alembic/            # Миграции БД
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-v2/            # Vue 3 приложение
│   ├── src/
│   │   ├── pages/          # Страницы (Dashboard, Activities, Training, Goals, Coach)
│   │   ├── components/     # Компоненты (layout, auth, common)
│   │   ├── stores/         # Pinia stores
│   │   └── api/            # API клиент
│   └── vite.config.ts
├── frontend-v2-dist/       # Билд фронтенда (генерируется npm run build)
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env                    # Секреты (не коммитить!)
└── .env.example            # Шаблон .env
```

---

## Деплой на сервер

```bash
# На сервере (Ubuntu/Debian)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git

git clone <repo-url> runapp
cd runapp

cp .env.example .env
nano .env   # заполнить все поля, APP_BASE_URL=https://yourdomain.com

# Собрать фронтенд локально и загрузить папку frontend-v2-dist/
# или установить Node.js на сервере:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
cd frontend-v2 && npm ci && npm run build && cd ..

docker compose up -d --build
```

Для HTTPS рекомендуется Nginx + Certbot на хосте, либо Traefik в Docker.
