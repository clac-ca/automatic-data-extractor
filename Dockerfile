# syntax=docker/dockerfile:1.7

##
## Automatic Data Extractor (ADE)
##
## Targets
## - production   : runtime image for API + worker + web
## - devcontainer : development image used by VS Code devcontainers
##
## Principles
## - Keep production lean and deterministic.
## - Keep development ergonomic without mutating containers at startup.
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

# ------------------------------------------------------------
# Toolchain sources.
# ------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin
FROM ${NODE_IMAGE} AS node-dev

# ------------------------------------------------------------
# backend-builder: install locked production Python environment.
# Output: /opt/venv
# ------------------------------------------------------------
FROM python-base AS backend-builder
WORKDIR /build/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      git \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv-bin /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ------------------------------------------------------------
# web-builder: compile frontend assets.
# ------------------------------------------------------------
FROM ${NODE_IMAGE} AS web-builder
WORKDIR /build/web
ARG APP_VERSION

COPY frontend/ade-web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY frontend/ade-web/ ./
RUN ADE_APP_VERSION="$APP_VERSION" npm run build

# ------------------------------------------------------------
# runtime-base: runtime-only OS deps, nginx config, static assets.
# ------------------------------------------------------------
FROM python-base AS runtime-base
WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      gettext-base \
      git \
      gosu \
      libpq5 \
      nginx \
      tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 -s /usr/sbin/nologin adeuser

COPY --from=web-builder --chown=adeuser:adeuser /build/web/dist /usr/share/nginx/html
COPY --chown=adeuser:adeuser frontend/ade-web/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --chown=adeuser:adeuser frontend/ade-web/nginx/default.conf.tmpl /etc/nginx/templates/default.conf.tmpl
COPY --chown=adeuser:adeuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]

RUN mkdir -p \
      /var/lib/ade/data \
      /var/cache/nginx \
      /var/run/nginx \
      /var/lib/nginx \
      /var/log/nginx \
    && chown -R adeuser:adeuser \
      /var/lib/ade \
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
COPY --from=backend-builder /opt/venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    ADE_APP_VERSION=${APP_VERSION} \
    ADE_APP_COMMIT_SHA=${APP_COMMIT_SHA} \
    PATH="/opt/venv/bin:$PATH"

EXPOSE 8000
CMD ["ade", "start"]

# ------------------------------------------------------------
# devcontainer: developer image.
# - build tools + git + libpq headers
# - uv + Node.js 22 toolchain
# - interactive shell user with passwordless sudo
# ------------------------------------------------------------
FROM python-base AS devcontainer
WORKDIR /workspaces/automatic-data-extractor

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      git \
      libpq-dev \
      sudo \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv-bin /uv /uvx /usr/local/bin/
COPY --from=node-dev /usr/local/bin/node /usr/local/bin/node
COPY --from=node-dev /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -sf ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN useradd -m -u 10001 -s /bin/bash adeuser \
    && usermod -aG sudo adeuser \
    && echo "adeuser ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/90-adeuser \
    && chmod 0440 /etc/sudoers.d/90-adeuser

USER adeuser
CMD ["sleep", "infinity"]
