# syntax=docker/dockerfile:1.6

# Keep base versions configurable but with sane defaults
ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20

# =============================================================================
# Stage 1: Frontend build (Vite SPA)
# =============================================================================
FROM node:${NODE_VERSION}-alpine AS frontend-build
WORKDIR /app

# Install frontend dependencies using only manifest files (cache-friendly)
COPY apps/ade-web/package*.json apps/ade-web/
RUN npm ci --prefix apps/ade-web --no-audit --no-fund

# Copy SPA sources and telemetry schemas required at build-time
COPY apps/ade-web apps/ade-web
COPY apps/ade-engine/src/ade_engine/schemas apps/ade-engine/src/ade_engine/schemas

# Build production bundle
RUN npm run build --prefix apps/ade-web

# =============================================================================
# Stage 2: Backend build (install Python packages)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS backend-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# System deps for building Python packages (kept out of final image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Copy minimal metadata first to maximize layer cache reuse
COPY README.md ./
COPY apps/ade-cli/pyproject.toml    apps/ade-cli/
COPY apps/ade-engine/pyproject.toml apps/ade-engine/
COPY apps/ade-api/pyproject.toml    apps/ade-api/

# Now copy full sources
COPY apps ./apps

# Install CLI, engine, and API into an isolated prefix (/install)
RUN python -m pip install -U pip \
    && python -m pip install --no-cache-dir --prefix=/install \
        ./apps/ade-cli \
        ./apps/ade-engine \
        ./apps/ade-api

# =============================================================================
# Stage 3: Runtime image (what actually runs in prod)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ADE_API_ROOT=/app/apps/ade-api \
    ADE_ALEMBIC_INI_PATH=/app/apps/ade-api/alembic.ini \
    ADE_ALEMBIC_MIGRATIONS_DIR=/app/apps/ade-api/migrations \
    ADE_SERVER_HOST=0.0.0.0 \
    ADE_SERVER_PORT=8000

WORKDIR /app

# OCI labels: nice to have in registries
LABEL org.opencontainers.image.title="automatic-data-extractor" \
      org.opencontainers.image.description="ADE — Automatic Data Extractor" \
      org.opencontainers.image.source="https://github.com/clac-ca/automatic-data-extractor"

# Bring in installed Python packages + console scripts
COPY --from=backend-build /install /usr/local

# Copy source tree (for migrations, templates, alembic.ini, etc.)
COPY apps ./apps

# Copy built SPA into FastAPI's static directory
COPY --from=frontend-build /app/apps/ade-web/dist \
    ./apps/ade-api/src/ade_api/web/static

# Create non-root user and data directory, then fix ownership
RUN groupadd -r ade && useradd -r -g ade ade \
    && mkdir -p /app/data/db /app/data/documents \
    && chown -R ade:ade /app

VOLUME ["/app/data"]
EXPOSE 8000

USER ade

CMD ["uvicorn", "ade_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
