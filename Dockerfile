# Multi-stage build: compile the React frontend, then run FastAPI which serves
# both the API (/api/*) and the built SPA (everything else) as one service.

# --- Stage 1: build the frontend ---
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # outputs /fe/dist

# --- Stage 2: backend runtime ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/static \
    DATA_DIR=/data
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /fe/dist ./static

EXPOSE 8000
# Migrate + serve via a real shell script (see backend/start.sh) so the host never
# has to expand ${PORT} itself.
CMD ["sh", "/app/start.sh"]
