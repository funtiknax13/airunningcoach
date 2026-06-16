#!/bin/sh
set -e

echo "⏳ Applying database migrations..."
alembic upgrade head
echo "✅ Migrations complete"

echo "🚀 Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --no-access-log \
    --proxy-headers \
    --forwarded-allow-ips='*'
