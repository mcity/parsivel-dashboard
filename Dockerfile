# Production image: builds the Vue frontend, then packages it with the Flask
# backend so a single container serves everything. The SQLite database is NOT
# in the image; it lives on a Docker volume mounted at /app/data and is kept
# current by scripts/sync_to_aws.py + scripts/ingest.py. See DEPLOY.md.

# --- Stage 1: frontend build ----------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend + built SPA -----------------------------------------
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
COPY backend/scripts/ingest.py ./scripts/ingest.py
COPY --from=frontend /build/dist ./static
RUN mkdir -p /app/data /incoming

VOLUME ["/app/data"]
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "wsgi:app"]
