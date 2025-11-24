# syntax=docker/dockerfile:1.6

ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20

# -----------------------------------------------------------------------------
# Stage 1: Build frontend (Vite SPA)
# -----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS web-build
WORKDIR /app

# Install frontend dependencies using only package manifests (better caching)
COPY apps/ade-web/package*.json apps/ade-web/
RUN npm ci --prefix apps/ade-web --no-audit --no-fund

# Copy source and telemetry schemas needed at build time
COPY apps/ade-web apps/ade-web
COPY apps/ade-engine/src/ade_engine/schemas apps/ade-engine/src/ade_engine/schemas

# Build production SPA bundle
RUN npm run build --prefix apps/ade-web

# -----------------------------------------------------------------------------
# Stage 2: Build backend / Python packages
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS backend-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# System deps to compile any native extensions during pip install
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Copy minimal metadata first for better caching
COPY README.md ./ \
     apps/ade-cli/pyproject.toml    apps/ade-cli/ \
     apps/ade-engine/pyproject.toml apps/ade-engine/ \
     apps/ade-api/pyproject.toml    apps/ade-api/

# Now copy the full apps tree
COPY apps ./apps

# Install CLI, engine, and API into /install so we can copy into runtime
RUN python -m pip install -U pip \
    && pip install --no-cache-dir --prefix=/install \
        ./apps/ade-cli \
        ./apps/ade-engine \
        ./apps/ade-api

# -----------------------------------------------------------------------------
# Stage 3: Runtime image
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    API_ROOT=/app/apps/ade-api \
    ALEMBIC_INI_PATH=/app/apps/ade-api/alembic.ini \
    ALEMBIC_MIGRATIONS_DIR=/app/apps/ade-api/migrations \
    ADE_SERVER_HOST=0.0.0.0 \
    ADE_SERVER_PORT=8000

WORKDIR /app

LABEL org.opencontainers.image.title="automatic-data-extractor" \
      org.opencontainers.image.description="ADE — Automatic Data Extractor" \
      org.opencontainers.image.source="https://github.com/clac-ca/automatic-data-extractor"

# Copy installed packages and console scripts from the build stage
COPY --from=backend-build /install /usr/local

# Copy source tree for Alembic configs, migrations, templates, etc.
COPY apps ./apps

# Copy built SPA into the API's static assets directory
COPY --from=web-build /app/apps/ade-web/dist ./apps/ade-api/src/ade_api/web/static

# Create dedicated user and data directory, then fix ownership
RUN groupadd -r ade && useradd -r -g ade ade \
    && mkdir -p /app/data/db /app/data/documents \
    && chown -R ade:ade /app

VOLUME ["/app/data"]
EXPOSE 8000

USER ade

CMD ["uvicorn", "ade_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
