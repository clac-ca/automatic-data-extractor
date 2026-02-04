# syntax=docker/dockerfile:1.7

##
## Automatic Data Extractor (ADE)
##
## Targets:
##   - production (default): production image (small, non-editable, no dev deps)
##   - development:      development image (editable install + dev deps)
##
## Examples:
##   docker build -t automatic-data-extractor:prod --target production .
##   docker build -t automatic-data-extractor:dev  --target development .
##

ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm
ARG NODE_IMAGE=node:20-bookworm-slim
ARG UV_VERSION=0.9.28

# ============================================================
# Base: shared Python runtime defaults
# ============================================================
FROM ${PYTHON_IMAGE} AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ============================================================
# uv: copy uv/uvx binaries from the official image
# ============================================================
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ============================================================
# python-build-base: common builder tooling for uv sync
# ============================================================
FROM python-base AS python-build-base
WORKDIR /app/backend

# OS packages needed to build Python deps (and install git-based deps).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      git \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (binary) into the builder.
COPY --from=uv /uv /uvx /usr/local/bin/

# Install the project environment into a standard, location-based venv.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

# ============================================================
# python-deps-prod: install production dependencies only
# (no project install; cached separately from source changes)
# ============================================================
FROM python-build-base AS python-deps-prod
COPY backend/pyproject.toml backend/uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# ============================================================
# python-build-prod: install the ADE project (non-editable)
# output: /opt/venv (contains console scripts like `ade`)
# ============================================================
FROM python-deps-prod AS python-build-prod
COPY backend/ ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ============================================================
# python-deps-dev: install dev dependencies only (no project)
# cached separately from source changes
# ============================================================
FROM python-build-base AS python-deps-dev
COPY backend/pyproject.toml backend/uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --dev

# ============================================================
# python-build-dev: install the ADE project (editable)
# IMPORTANT: the editable install path is /app/backend
# ============================================================
FROM python-deps-dev AS python-build-dev
COPY backend/ ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --dev

# ============================================================
# web-build: build frontend static assets
# ============================================================
FROM ${NODE_IMAGE} AS web-build
WORKDIR /web

COPY frontend/ade-web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY frontend/ade-web/ ./
RUN npm run build

# ============================================================
# runtime-base: runtime OS deps + nginx config + built web assets
# ============================================================
FROM python-base AS runtime-base
WORKDIR /app

# Runtime OS dependencies only.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      gettext-base \
      gosu \
      libpq5 \
      nginx \
      tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user (keep the existing convention).
RUN useradd -m -u 10001 -s /usr/sbin/nologin adeuser

# Static web assets and nginx config template.
COPY --from=web-build /web/dist /usr/share/nginx/html
COPY frontend/ade-web/nginx/nginx.conf /etc/nginx/nginx.conf
COPY frontend/ade-web/nginx/default.conf.tmpl /etc/nginx/templates/default.conf.tmpl
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Writable runtime directories for nginx + ADE.
RUN mkdir -p \
      /app/backend/data \
      /var/cache/nginx \
      /var/run/nginx \
      /var/lib/nginx \
      /var/log/nginx \
    && chown -R adeuser:adeuser \
      /app \
      /etc/nginx/conf.d \
      /etc/nginx/templates \
      /usr/share/nginx/html \
      /var/cache/nginx \
      /var/run/nginx \
      /var/lib/nginx \
      /var/log/nginx

# ============================================================
# development: development image (editable install + dev deps)
# ============================================================
FROM runtime-base AS development

# Dev conveniences (keep minimal but practical).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      git \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Devcontainer shells require a valid interactive shell for the remote user.
RUN usermod -s /bin/bash adeuser

# Include uv for local workflow convenience inside devcontainers.
COPY --from=uv /uv /uvx /usr/local/bin/

# Copy the dev virtualenv (includes dev deps + editable ADE install).
COPY --from=python-build-dev /opt/venv /opt/venv

# Ensure the editable source path exists in the image.
# (Devcontainers will typically bind-mount the repo at /app, replacing this.)
COPY --from=python-build-dev /app/backend /app/backend

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["ade", "start"]

# ============================================================
# production: production image (small, no dev deps, non-editable)
# ============================================================
FROM runtime-base AS production

# Copy the production virtualenv (includes ADE console scripts).
COPY --from=python-build-prod /opt/venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["ade", "start"]
