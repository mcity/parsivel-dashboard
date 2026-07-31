# Production image for the demo deployment: builds the Vue frontend, then
# packages it with the Flask backend and the SQLite data snapshot so a single
# container serves everything. See DEPLOY.md.

# --- Stage 1: frontend build ----------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend + built SPA + data snapshot -------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install uv

WORKDIR /app

COPY backend/pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY backend/app ./app
COPY backend/wsgi.py ./
COPY --from=frontend /build/dist ./static
COPY backend/data/parsivel.db ./data/parsivel.db

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "wsgi:app"]
