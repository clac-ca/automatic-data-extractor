# syntax=docker/dockerfile:1.7

##
## Automatic Data Extractor (ADE)
##
## Targets
## - production   : runtime image for API + worker + web
## - devcontainer : development image used by VS Code devcontainers
##

ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm
ARG NODE_IMAGE=node:22-bookworm-slim
ARG UV_VERSION=0.9.28
ARG APP_VERSION=unknown
ARG APP_COMMIT_SHA=unknown

# ------------------------------------------------------------
# Shared Python defaults.
# ------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Keep APT artifacts cacheable with BuildKit cache mounts.
RUN rm -f /etc/apt/apt.conf.d/docker-clean

# ------------------------------------------------------------
# Toolchain sources.
# ------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin
FROM ${NODE_IMAGE} AS node-dev

# ------------------------------------------------------------
# backend-builder: install locked production Python environment.
# Output: /app/.venv
# ------------------------------------------------------------
FROM python-base AS backend-builder
WORKDIR /build/backend

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      git

COPY --from=uv-bin /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy

COPY backend/pyproject.toml backend/uv.lock ./
COPY VERSION /build/VERSION
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-install-project --no-dev

COPY --link backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-dev --no-editable

# ------------------------------------------------------------
# web-builder: compile frontend assets.
# ------------------------------------------------------------
FROM ${NODE_IMAGE} AS web-builder
WORKDIR /build/web

COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --no-audit --no-fund

COPY --link frontend/ ./
RUN npm run build

# ------------------------------------------------------------
# runtime-base: runtime-only OS deps, nginx config, static assets.
# ------------------------------------------------------------
FROM python-base AS runtime-base
WORKDIR /

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      gettext-base \
      git \
      gosu \
      libpq5 \
      nginx \
      tini

RUN useradd -m -u 10001 -s /usr/sbin/nologin adeuser

COPY --link --from=web-builder --chown=10001:10001 /build/web/dist /usr/share/nginx/html
COPY --link --chown=10001:10001 frontend/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --link --chown=10001:10001 frontend/nginx/default.conf.tmpl /etc/nginx/templates/default.conf.tmpl
COPY --link --chown=10001:10001 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]

RUN mkdir -p \
      /app/data \
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

# ------------------------------------------------------------
# production: shipped image.
# ------------------------------------------------------------
FROM runtime-base AS production
ARG APP_VERSION
ARG APP_COMMIT_SHA
COPY --link --from=backend-builder /app/.venv /app/.venv

ENV VIRTUAL_ENV=/app/.venv \
    ADE_APP_VERSION=${APP_VERSION} \
    ADE_APP_COMMIT_SHA=${APP_COMMIT_SHA} \
    PATH="/app/.venv/bin:$PATH"

# Stamp version.json here so APP_VERSION changes don't invalidate web-builder cache.
RUN python - <<'PY'
import json
import os
from pathlib import Path

path = Path("/usr/share/nginx/html/version.json")
version = (os.environ.get("ADE_APP_VERSION") or "").strip() or "unknown"
path.write_text(json.dumps({"version": version}, indent=2) + "\n", encoding="utf-8")
PY

EXPOSE 8000
CMD ["ade", "start"]

# ------------------------------------------------------------
# devcontainer: developer image.
# - build tools + git + libpq headers
# - uv + Node.js 22 toolchain
# - interactive shell user with passwordless sudo
# ------------------------------------------------------------
FROM python-base AS devcontainer
WORKDIR /app/src

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      git \
      libpq-dev \
      sudo

COPY --from=uv-bin /uv /uvx /usr/local/bin/
COPY --from=node-dev /usr/local/bin/node /usr/local/bin/node
COPY --from=node-dev /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -sf ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN useradd -m -u 10001 -s /bin/bash adeuser \
    && mkdir -p /app/src /app/.venv /app/data \
    && chown -R adeuser:adeuser /app \
    && usermod -aG sudo adeuser \
    && echo "adeuser ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/90-adeuser \
    && chmod 0440 /etc/sudoers.d/90-adeuser

USER adeuser
CMD ["sleep", "infinity"]
