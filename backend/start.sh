#!/bin/sh
set -e
# Apply DB migrations, then serve. Bind 0.0.0.0 on the platform's $PORT (Railway/
# Render inject it); fall back to 8000 locally. exec so uvicorn is PID 1 and gets
# signals directly. Kept as a real shell script so no host config has to expand
# ${PORT} — that mangling is what made the healthcheck never come up.
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
