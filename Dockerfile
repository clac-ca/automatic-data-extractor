# syntax=docker/dockerfile:1.6

# Base versions (override at build time if needed)
ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20

# =============================================================================
# Stage 1: Frontend build (Vite SPA)
# =============================================================================
FROM node:${NODE_VERSION}-alpine AS frontend-build

# We'll build the SPA from here:
WORKDIR /app/apps/ade-web

# Install frontend dependencies using only manifest files (better caching)
COPY apps/ade-web/package*.json ./
RUN npm ci --no-audit --no-fund

# Copy SPA sources and telemetry schemas required at build time
COPY apps/ade-web/ ./
COPY apps/ade-engine/src/ade_engine/schemas ../ade-engine/src/ade_engine/schemas

# Build production bundle
RUN npm run build

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
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/microsoft-prod.gpg] https://packages.microsoft.com/config/debian/12/prod.list" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends build-essential git unixodbc unixodbc-dev msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Copy minimal metadata first to maximize layer cache reuse
COPY README.md ./
COPY apps/ade-cli/pyproject.toml    apps/ade-cli/
COPY apps/ade-engine/pyproject.toml apps/ade-engine/
COPY apps/ade-api/pyproject.toml    apps/ade-api/

RUN python -m pip install -U pip

# Now copy full sources
COPY apps ./apps

# Install CLI, engine, and API into an isolated prefix (/install)
RUN python -m pip install --no-cache-dir --prefix=/install \
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
    API_ROOT=/app/apps/ade-api \
    ALEMBIC_INI_PATH=/app/apps/ade-api/alembic.ini \
    ALEMBIC_MIGRATIONS_DIR=/app/apps/ade-api/migrations

WORKDIR /app

# System deps for pyodbc / Azure SQL connectivity (runtime only)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/microsoft-prod.gpg] https://packages.microsoft.com/config/debian/12/prod.list" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends unixodbc msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# OCI labels: nice to have in registries
LABEL org.opencontainers.image.title="automatic-data-extractor" \
      org.opencontainers.image.description="ADE — Automatic Data Extractor" \
      org.opencontainers.image.source="https://github.com/clac-ca/automatic-data-extractor"

# Bring in installed Python packages + console scripts
COPY --from=backend-build /install /usr/local

# Copy app source tree (migrations, templates, etc.)
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
